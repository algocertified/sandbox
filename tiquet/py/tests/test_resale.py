import base64
import pytest

from algosdk.error import AlgodHTTPError
from algosdk.future import transaction
from fixtures import *
from tiquet.common import constants


# Tests are flaky, sometimes failing because account funds change by unexpected
# amounts.


def test_resale_success(
    tiquet_io_account,
    issuer_account,
    buyer_account,
    second_buyer_account,
    tiquet_resale_price,
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
    # Check issuer account is credited royalty amount.
    royalty_amount = get_tiquet_royalty_amount(tiquet_resale_price, issuer_tiquet_royalty_numerator, issuer_tiquet_royalty_denominator)
    assert issuer_balance_after - issuer_balance_before == royalty_amount
    # Check second buyer account is debited tiquet price, tiquet.io processing
    # fee, royalty, and fees for 5 txns.
    assert (
        second_buyer_balance_after - second_buyer_balance_before
        == -1 * tiquet_resale_price
        - constants.TIQUET_IO_PROCESSING_FEE
        - royalty_amount
        - 5 * algod_params.fee
    )


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
    # Check second buyer account is debited fees for 1 txn.
    assert (
        second_buyer_balance_after - second_buyer_balance_before
        == -1 * algod_params.fee
    )


def get_tiquet_royalty_amount(tiquet_price, royalty_numerator, royalty_denominator):
    return int((royalty_numerator / royalty_denominator) * tiquet_price)
