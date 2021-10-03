import base64
import pytest

from fixtures import *
from tiquet.common import constants


# Tests are flaky, sometimes failing because account funds change by unexpected
# amounts.


def test_post_for_resale_success(
    buyer_account,
    tiquet_issuance_info,
    initial_sale,
    buyer,
    tiquet_resale_price,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])

    buyer.post_for_resale(
        tiquet_id=tiquet_id,
        app_id=app_id,
        tiquet_price=tiquet_resale_price,
    )

    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is still in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct value.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
        var_type=2,
        var_val=tiquet_resale_price,
    )
    # Check tiquet for-sale flag global variable is set to true.
    assert algorand_helper.has_global_var(
        app_id=app_id,
        var_key=constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME,
        var_type=2,
        var_val=1,
    )
    # Check buyer account is debited fee for 1 txn.
    assert buyer_balance_after - buyer_balance_before == -1 * algod_params.fee
