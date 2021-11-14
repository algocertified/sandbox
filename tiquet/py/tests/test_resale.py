import base64
import pytest

from algosdk.error import AlgodHTTPError
from algosdk.future import transaction
from fixtures import *
from tiquet.common import constants


# Tests are flaky, sometimes failing because account funds change by unexpected
# amounts.


@pytest.mark.batch("1")
def test_resale_success(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    second_buyer.buy_tiquet(
        tiquet_id=tiquet_id,
        app_id=app_id,
        escrow_lsig=escrow_lsig,
        issuer_account=issuer_account["pk"],
        seller_account=buyer_account["pk"],
        amount=tiquet_resale_price,
    )

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id)
    # Check tiquet is no longer in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the correct
        # resale price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to false.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 0},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account is credited tiquet amount.
    assert buyer_balance_after - buyer_balance_before == tiquet_resale_price
    # Check tiquet.io account is credited processing fee.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    assert tiquet_io_balance_after - tiquet_io_balance_before == processing_fee
    # Check issuer account is credited royalty amount.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    assert issuer_balance_after - issuer_balance_before == royalty_amount
    # Check second buyer account is debited tiquet price, tiquet.io processing
    # fee, royalty, and fees for 5 txns.
    assert (
        second_buyer_balance_after - second_buyer_balance_before
        == -1 * tiquet_resale_price
        - processing_fee
        - royalty_amount
        - 5 * algod_params.fee
    )


@pytest.mark.batch("1")
def test_resale_before_post(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_price,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    initial_sale,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    with pytest.raises(AlgodHTTPError) as e:
        second_buyer.buy_tiquet(
            tiquet_id=tiquet_id,
            app_id=app_id,
            escrow_lsig=escrow_lsig,
            issuer_account=issuer_account["pk"],
            seller_account=buyer_account["pk"],
            amount=tiquet_price,
        )
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the original
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to false.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 0},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account is debited fees for 1 txn.
    assert (
        second_buyer_balance_after - second_buyer_balance_before
        == -1 * algod_params.fee
    )


@pytest.mark.batch("1")
def test_seller_tiquet_transfer(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Tiquet transfer from seller to buyer.
    txn = transaction.AssetTransferTxn(
        sender=buyer_account["pk"],
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
    )
    stxn = txn.sign(buyer_account["sk"])
    with pytest.raises(AlgodHTTPError) as e:
        algorand_helper.send_and_wait_for_txn(stxn)
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("1")
def test_seller_tiquet_transfer_through_escrow(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Tiquet transfer from escrow to buyer.
    txn = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
    )
    stxn = txn.sign(buyer_account["sk"])
    with pytest.raises(AlgodHTTPError) as e:
        algorand_helper.send_and_wait_for_txn(stxn)
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("1")
def test_buyer_stealing_tiquet(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Tiquet transfer from escrow to buyer, initiated by the buyer.
    txn = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
    )
    stxn = txn.sign(second_buyer_account["sk"])
    with pytest.raises(AlgodHTTPError) as e:
        algorand_helper.send_and_wait_for_txn(stxn)
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("1")
def test_resale_no_tiquet_payment(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )

    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to issuer.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("1")
def test_resale_incorrect_tiquet_payment(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price - 1,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to issuer.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])
    stxn5 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("1")
def test_resale_tiquet_payment_to_nonseller(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    fraudster_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to fraudster.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to issuer.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])
    stxn5 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


@pytest.mark.batch("1")
def test_resale_no_royalty(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("1")
def test_resale_incorrect_royalty(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to issuer.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount - 1,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])
    stxn5 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("2")
def test_resale_royalty_to_nonseller(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    fraudster_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to fraudster.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])
    stxn5 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


@pytest.mark.batch("2")
def test_resale_no_processing_fee(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Royalty fee to fraudster.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("2")
def test_resale_incorrect_processing_fee(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee - 1,
    )

    # Royalty fee to fraudster.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])
    stxn5 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before


@pytest.mark.batch("2")
def test_resale_processing_fee_to_nonseller(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    fraudster_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to fraudster.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to issuer.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])
    stxn5 = txn4.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


@pytest.mark.batch("2")
def test_resale_from_fraudster(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    fraudster_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    fraudster_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    fraudster_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        foreign_apps=[administrator.constants_app_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to fraudster.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to issuer.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid

    stxn1 = txn1.sign(fraudster_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(fraudster_account["sk"])
    stxn4 = txn4.sign(fraudster_account["sk"])
    stxn5 = txn5.sign(fraudster_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


@pytest.mark.batch("2")
def test_resale_with_extra_txn(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    fraudster_account,
    tiquet_resale_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    tiquet_issuance_info,
    post_for_resale,
    administrator,
    buyer,
    second_buyer,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    second_buyer.tiquet_opt_in(tiquet_id)

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_before = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    # Application call to execute sale.
    txn1 = transaction.ApplicationNoOpTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"], buyer_account["pk"]],
        foreign_apps=[administrator.constants_app_id],
        foreign_assets=[tiquet_id],
        app_args=[constants.TIQUET_APP_RESALE_COMMAND],
    )

    # Tiquet transfer to buyer.
    txn2 = transaction.AssetTransferTxn(
        sender=escrow_lsig.address(),
        sp=algod_params,
        receiver=second_buyer_account["pk"],
        amt=1,
        index=tiquet_id,
        revocation_target=buyer_account["pk"],
    )

    # Tiquet payment to seller.
    txn3 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=buyer_account["pk"],
        amt=tiquet_resale_price,
    )

    # Processing fee to tiquet.io.
    processing_fee = get_tiquet_processing_fee(
        tiquet_resale_price,
        tiquet_processing_fee_numerator,
        tiquet_processing_fee_denominator,
    )
    txn4 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=tiquet_io_account["pk"],
        amt=processing_fee,
    )

    # Royalty fee to issuer.
    royalty_amount = get_tiquet_royalty_amount(
        tiquet_resale_price,
        issuer_tiquet_royalty_numerator,
        issuer_tiquet_royalty_denominator,
    )
    txn5 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=issuer_account["pk"],
        amt=royalty_amount,
    )

    # Extra txn.
    txn6 = transaction.PaymentTxn(
        sender=second_buyer_account["pk"],
        sp=algod_params,
        receiver=fraudster_account["pk"],
        amt=10,
    )

    gid = transaction.calculate_group_id([txn1, txn2, txn3, txn4, txn5, txn6])
    txn1.group = gid
    txn2.group = gid
    txn3.group = gid
    txn4.group = gid
    txn5.group = gid
    txn6.group = gid

    stxn1 = txn1.sign(second_buyer_account["sk"])
    stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
    assert stxn2.verify()
    stxn3 = txn3.sign(second_buyer_account["sk"])
    stxn4 = txn4.sign(second_buyer_account["sk"])
    stxn5 = txn5.sign(second_buyer_account["sk"])
    stxn6 = txn5.sign(second_buyer_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algodclient.send_transactions([stxn1, stxn2, stxn3, stxn4, stxn5, stxn6])
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    second_buyer_balance_after = algorand_helper.get_amount(second_buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is still in possession of seller (original buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet is not in possession of second buyer.
    assert algorand_helper.has_asset(second_buyer_account["pk"], tiquet_id, amount=0)

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the resale
        # price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": tiquet_resale_price},
        # Check tiquet royalty global variables are set and assigned the correct
        # values.
        constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_numerator
        },
        constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME: {
            "value": issuer_tiquet_royalty_denominator
        },
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_global_vars.keys())
        == expected_global_vars
    )

    # Check seller (original buyer) account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check second buyer account balance is unchanged.
    assert second_buyer_balance_after == second_buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before


def get_tiquet_processing_fee(
    tiquet_price, processing_fee_numerator, processing_fee_denominator
):
    return int((processing_fee_numerator / processing_fee_denominator) * tiquet_price)


def get_tiquet_royalty_amount(tiquet_price, royalty_numerator, royalty_denominator):
    return int((royalty_numerator / royalty_denominator) * tiquet_price)
