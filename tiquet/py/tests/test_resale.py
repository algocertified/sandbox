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
    # Check tiquet is no longer in possession of seller (first buyer).
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id, amount=0)
    # Check tiquet price global variable is set and is assigned the correct value.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type=2,
        var_val=tiquet_resale_price,
    )
    # Check tiquet for-sale flag global variable is set to false.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type=2,
        var_val=0,
    )

    # Check tiquet.io account is credited processing fee.
    assert (
        tiquet_io_balance_after - tiquet_io_balance_before
        == constants.TIQUET_IO_PROCESSING_FEE
    )
    # Check seller (first buyer) account is credited tiquet amount.
    assert buyer_balance_after - buyer_balance_before == tiquet_resale_price
    # Check issuer account is credited royalty amount.
    # TODO
    assert issuer_balance_after - issuer_balance_before == 1000
    # Check second buyer account is debited tiquet price, tiquet.io processing
    # fee, royalty, and fees for 5 txns.
    # TODO
    assert (
        second_buyer_balance_after - second_buyer_balance_before
        == -1 * tiquet_resale_price
        - constants.TIQUET_IO_PROCESSING_FEE
        - 1000
        - 5 * algod_params.fee
    )
