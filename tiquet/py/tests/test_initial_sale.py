import base64
import pytest
import uuid

from algosdk.error import AlgodHTTPError
from algosdk.future import transaction
from fixtures import *
from tiquet.common.algorand_helper import AlgorandHelper
from tiquet.tiquet_client import TiquetClient
from tiquet.tiquet_issuer import TiquetIssuer


def test_initial_sale_success(
    accounts,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
    app_fpath,
    clear_fpath,
    escrow_fpath,
):
    # Get issuer algorand account, with public and secret keys.
    issuer_account = accounts.get_issuer_account()
    logger.debug("Issuer address: {}".format(issuer_account["pk"]))

    issuer = TiquetIssuer(
        pk=issuer_account["pk"],
        sk=issuer_account["sk"],
        mnemonic=issuer_account["mnemonic"],
        app_fpath=app_fpath,
        clear_fpath=clear_fpath,
        escrow_fpath=escrow_fpath,
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
    )

    tiquet_name = uuid.uuid4()
    tiquet_price = 100000000000
    tiquet_id, app_id, escrow_lsig = issuer.issue_tiquet(tiquet_name, tiquet_price)

    logger.debug("Tiquet Id: {}".format(tiquet_id))
    logger.debug("App Id: {}".format(app_id))
    logger.debug("Escrow address: {}".format(escrow_lsig.address()))

    buyer_account = accounts.get_buyer_account()
    logger.debug("Buyer address: {}".format(buyer_account["pk"]))

    buyer = TiquetClient(
        pk=buyer_account["pk"],
        sk=buyer_account["sk"],
        mnemonic=buyer_account["mnemonic"],
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
        escrow_lsig=escrow_lsig,
    )

    issuer_amount_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_amount_before = algorand_helper.get_amount(buyer_account["pk"])

    buyer.buy_tiquet(
        tiquet_id=tiquet_id,
        app_id=app_id,
        issuer_account=issuer_account["pk"],
        seller_account=issuer_account["pk"],
        amount=tiquet_price,
    )

    issuer_amount_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_amount_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is in possession of buyer.    
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is no longer in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id, amount=0)
    # Check issuer account is credited tiquet amount.
    assert issuer_amount_after - issuer_amount_before == tiquet_price
    # Check buyer account is debited tiquet price and fees for 3 txns.
    assert (
        buyer_amount_after - buyer_amount_before
        == -1 * tiquet_price - 3 * algod_params.fee
    )

def test_initial_sale_no_payment(
    accounts,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
    app_fpath,
    clear_fpath,
    escrow_fpath,
):
    # Get issuer algorand account, with public and secret keys.
    issuer_account = accounts.get_issuer_account()
    logger.debug("Issuer address: {}".format(issuer_account["pk"]))

    issuer = TiquetIssuer(
        pk=issuer_account["pk"],
        sk=issuer_account["sk"],
        mnemonic=issuer_account["mnemonic"],
        app_fpath=app_fpath,
        clear_fpath=clear_fpath,
        escrow_fpath=escrow_fpath,
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
    )

    tiquet_name = uuid.uuid4()
    tiquet_price = 100000000000
    tiquet_id, app_id, escrow_lsig = issuer.issue_tiquet(tiquet_name, tiquet_price)

    logger.debug("Tiquet Id: {}".format(tiquet_id))
    logger.debug("App Id: {}".format(app_id))
    logger.debug("Escrow address: {}".format(escrow_lsig.address()))

    buyer_account = accounts.get_buyer_account()
    logger.debug("Buyer address: {}".format(buyer_account["pk"]))

    buyer = TiquetClient(
        pk=buyer_account["pk"],
        sk=buyer_account["sk"],
        mnemonic=buyer_account["mnemonic"],
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
        escrow_lsig=escrow_lsig,
    )

    buyer.tiquet_opt_in(tiquet_id)

    issuer_amount_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_amount_before = algorand_helper.get_amount(buyer_account["pk"])

    with pytest.raises(AlgodHTTPError) as e:
        txn1 = transaction.ApplicationNoOpTxn(
            sender=buyer_account["pk"],
            sp=algod_params,
            index=app_id,
            accounts=[issuer_account["pk"]],
            foreign_assets=[tiquet_id],
        )

        txn2 = transaction.AssetTransferTxn(
            sender=escrow_lsig.address(),
            sp=algod_params,
            receiver=buyer_account["pk"],
            amt=1,
            index=tiquet_id,
            revocation_target=issuer_account["pk"],
        )

        gid = transaction.calculate_group_id([txn1, txn2])
        txn1.group = gid
        txn2.group = gid

        stxn1 = txn1.sign(buyer_account["sk"])
        stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
        assert stxn2.verify()

        txid = algodclient.send_transactions([stxn1, stxn2])
        algorand_helper.wait_for_confirmation(txid)

        assert "transaction rejected by ApprovalProgram" in e.message

    issuer_amount_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_amount_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is not in possession of buyer.    
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check issuer account balance is unchanged.
    assert issuer_amount_after == issuer_amount_before
    # Check buyer account balance is unchanged.
    assert (
        buyer_amount_after - buyer_amount_before
        == 0
    )

def test_initial_sale_insufficient_payment_amount(
    accounts,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
    app_fpath,
    clear_fpath,
    escrow_fpath,
):
    # Get issuer algorand account, with public and secret keys.
    issuer_account = accounts.get_issuer_account()
    logger.debug("Issuer address: {}".format(issuer_account["pk"]))

    issuer = TiquetIssuer(
        pk=issuer_account["pk"],
        sk=issuer_account["sk"],
        mnemonic=issuer_account["mnemonic"],
        app_fpath=app_fpath,
        clear_fpath=clear_fpath,
        escrow_fpath=escrow_fpath,
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
    )

    tiquet_name = uuid.uuid4()
    tiquet_price = 100000000000
    tiquet_id, app_id, escrow_lsig = issuer.issue_tiquet(tiquet_name, tiquet_price)

    logger.debug("Tiquet Id: {}".format(tiquet_id))
    logger.debug("App Id: {}".format(app_id))
    logger.debug("Escrow address: {}".format(escrow_lsig.address()))

    buyer_account = accounts.get_buyer_account()
    logger.debug("Buyer address: {}".format(buyer_account["pk"]))

    buyer = TiquetClient(
        pk=buyer_account["pk"],
        sk=buyer_account["sk"],
        mnemonic=buyer_account["mnemonic"],
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
        escrow_lsig=escrow_lsig,
    )

    issuer_amount_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_amount_before = algorand_helper.get_amount(buyer_account["pk"])

    with pytest.raises(AlgodHTTPError) as e:
        buyer.buy_tiquet(
            tiquet_id=tiquet_id,
            app_id=app_id,
            issuer_account=issuer_account["pk"],
            seller_account=issuer_account["pk"],
            amount=tiquet_price - 1,
        )
        assert "transaction rejected by ApprovalProgram" in e.message

    issuer_amount_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_amount_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is not in possession of buyer.    
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check issuer account balance is unchanged.
    assert issuer_amount_after == issuer_amount_before
    # Check buyer account is debited only fee for 1 asset opt-in txn.
    assert (
        buyer_amount_after - buyer_amount_before
        == -1 * algod_params.fee
    )
