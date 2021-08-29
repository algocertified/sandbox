import base64
import pytest

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

    tiquet_price = 1000000000000000
    tiquet_id, app_id, escrow_lsig = issuer.issue_tiquet(tiquet_price)

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

    issuer_info_before = algodclient.account_info(issuer_account["pk"])
    buyer_info_before = algodclient.account_info(buyer_account["pk"])

    buyer.buy_tiquet(
        tiquet_id=tiquet_id,
        app_id=app_id,
        issuer_account=issuer_account["pk"],
        seller_account=issuer_account["pk"],
        amount=tiquet_price,
    )

    issuer_info_after = algodclient.account_info(issuer_account["pk"])
    buyer_info_after = algodclient.account_info(buyer_account["pk"])

    # Check tiquet is in possession of buyer.
    assert all(
        asset["amount"] == 0
        for asset in issuer_info_after["assets"]
        if asset["asset-id"] == tiquet_id
    )
    # Check tiquet is no longer in possession of issuer.
    assert all(
        asset["amount"] == 1
        for asset in buyer_info_after["assets"]
        if asset["asset-id"] == tiquet_id
    )
    # Check issuer account is credited tiquet amount.
    assert issuer_info_after["amount"] - issuer_info_before["amount"] == tiquet_price
    # Check buyer account is debited tiquet price and fees for 3 txns.
    assert (
        buyer_info_after["amount"] - buyer_info_before["amount"]
        == -1 * tiquet_price - 3 * algod_params.fee
    )
