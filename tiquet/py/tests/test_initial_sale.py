import base64
import pytest

from algosdk.error import AlgodHTTPError
from algosdk.future import transaction
from fixtures import *
from tiquet.common import constants


# Tests are flaky, sometimes failing because account funds change by unexpected
# amounts.


def test_initial_sale_success(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])

    buyer.buy_tiquet(
        tiquet_id=tiquet_id,
        app_id=app_id,
        issuer_account=issuer_account["pk"],
        seller_account=issuer_account["pk"],
        amount=tiquet_price,
    )

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is no longer in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id, amount=0)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is set to false.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=0,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account is credited processing fee.
    assert (
        tiquet_io_balance_after - tiquet_io_balance_before
        == constants.TIQUET_IO_PROCESSING_FEE
    )
    # Check issuer account is credited tiquet amount.
    assert issuer_balance_after - issuer_balance_before == tiquet_price
    # Check buyer account is debited tiquet price and fees for 4 txns.
    assert (
        buyer_balance_after - buyer_balance_before
        == -1 * tiquet_price - constants.TIQUET_IO_PROCESSING_FEE - 4 * algod_params.fee
    )


def test_initial_sale_no_tiquet_payment(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"]],
        foreign_assets=[tiquet_id],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=issuer_account["pk"],
    )

    # Processing fee to tiquet.io.
    txn3 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=constants.TIQUET_IO_PROCESSING_FEE,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid

    stxn1 = txn1.sign(buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        txid = algodclient.send_transactions([stxn1, stxn2, stxn3])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is not in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is still set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=1,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check buyer account balance is unchanged.
    assert buyer_balance_after - buyer_balance_before == 0


def test_initial_sale_insufficient_payment_amount(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])

    with pytest.raises(AlgodHTTPError) as e:
        buyer.buy_tiquet(
            tiquet_id=tiquet_id,
            app_id=app_id,
            issuer_account=issuer_account["pk"],
            seller_account=issuer_account["pk"],
            amount=tiquet_price - 1,
        )
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is not in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is still set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=1,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check buyer account is debited only fee for 1 asset opt-in txn.
    assert buyer_balance_after - buyer_balance_before == -1 * algod_params.fee


def test_initial_sale_payment_to_non_issuer(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    fraudster_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"]],
        foreign_assets=[tiquet_id],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=issuer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=tiquet_price,
    )

    # Processing fee to tiquet.io.
    txn4 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=constants.TIQUET_IO_PROCESSING_FEE,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid

    stxn1 = txn1.sign(buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(buyer_account["sk"])
    stxn4 = txn4.sign(buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        txid = algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is not in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is still set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=1,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check buyer account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


def test_initial_sale_no_processing_fee(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"]],
        foreign_assets=[tiquet_id],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=issuer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=tiquet_price,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid

    stxn1 = txn1.sign(buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        txid = algodclient.send_transactions([stxn1, stxn2, stxn3])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is not in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is still set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=1,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check buyer account balance is unchanged.
    assert buyer_balance_after - buyer_balance_before == 0


def test_initial_sale_processing_fee_to_non_tiquet_io(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    fraudster_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"]],
        foreign_assets=[tiquet_id],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=issuer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=tiquet_price,
    )

    # Processing fee to fraudster.
    txn4 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=constants.TIQUET_IO_PROCESSING_FEE,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid

    stxn1 = txn1.sign(buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(buyer_account["sk"])
    stxn4 = txn4.sign(buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        txid = algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is not in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is still set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=1,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check buyer account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


def test_initial_sale_from_fraudster(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    fraudster_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=fraudster_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"]],
        foreign_assets=[tiquet_id],
    )

    # Tiquet transfer to fraudster.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=issuer_account["pk"],
    )

    # Send Tiquet payment from buyer to seller.
    txn3 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=tiquet_price,
    )

    # Processing fee to tiquet.io from buyer.
    txn4 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=constants.TIQUET_IO_PROCESSING_FEE,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid

    stxn1 = txn1.sign(fraudster_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(fraudster_account["sk"])
    stxn4 = txn4.sign(fraudster_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        txid = algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is not in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is still set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=1,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check buyer account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


def test_initial_sale_with_fake_escrow(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    tiquet_price,
    issuer,
    tiquet_issuance_info,
    buyer,
    success_teal_fpath,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer.tiquet_opt_in(tiquet_id)

    with open(success_teal_fpath, "rt") as f:
        fake_escrow_prog = base64.b64decode(algodclient.compile(f.read())["result"])
    fake_escrow_lsig = transaction.LogicSigAccount(fake_escrow_prog)
    fake_escrow_lsig_address = fake_escrow_lsig.address()

    txn = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=fake_escrow_lsig_address,
        amt=1000000,
    )

    stxn = txn.sign(buyer_account["sk"])
    txid = algorand_helper.send_and_wait_for_txn(stxn)
    algodclient.pending_transaction_info(txid)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"]],
        foreign_assets=[tiquet_id],
    )

    # Tiquet transfer to fraudster.
    txn2 = transaction.AssetTransferTxn(
        sender=fake_escrow_lsig_address,
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=issuer_account["pk"],
    )

    # Send Tiquet payment from buyer to seller.
    txn3 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=tiquet_price,
    )

    # Processing fee to tiquet.io from buyer.
    txn4 = transaction.PaymentTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=10,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid

    stxn1 = txn1.sign(buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(buyer_account["sk"])
    stxn4 = txn4.sign(buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        txid = algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is not in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet is still in possession of issuer.
    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=tiquet_price,
    )
    # Check tiquet for-sale flag global variable is still set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type="int",
        var_val=1,
    )
    # Check escrow address global variable is set and is assigned the correct address.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME,
        var_type="addr",
        var_val=escrow_lsig.address(),
    )
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check buyer account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
