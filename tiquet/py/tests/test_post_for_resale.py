import base64
import pytest

from algosdk.error import AlgodHTTPError
from algosdk.future import transaction
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
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
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

    # Check buyer account is debited fee for 1 txn.
    assert buyer_balance_after - buyer_balance_before == -1 * algod_params.fee


def test_update_resale_price_success(
    buyer_account,
    tiquet_issuance_info,
    initial_sale,
    buyer,
    tiquet_resale_price,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
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

    new_tiquet_resale_price = 300000000000

    buyer.post_for_resale(
        tiquet_id=tiquet_id,
        app_id=app_id,
        tiquet_price=new_tiquet_resale_price,
    )

    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])

    # Check tiquet is still in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)
    # Check tiquet price global variable is set and is assigned the correct price.

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the correct,
        # most recent, resale price.
        constants.TIQUET_PRICE_GLOBAL_VAR_NAME: {"value": new_tiquet_resale_price},
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

    # Check buyer account is debited fee for 2 txns.
    assert buyer_balance_after - buyer_balance_before == -2 * algod_params.fee


def test_post_for_resale_from_fraudster(
    buyer_account,
    fraudster_account,
    tiquet_issuance_info,
    initial_sale,
    buyer,
    tiquet_price,
    tiquet_resale_price,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    buyer_balance_before = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    txn = transaction.ApplicationNoOpTxn(
        sender=fraudster_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[buyer_account["pk"]],
        foreign_assets=[tiquet_id],
        app_args=[constants.TIQUET_APP_POST_FOR_RESALE_COMMAND, tiquet_resale_price],
    )
    stxn = txn.sign(fraudster_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algorand_helper.send_and_wait_for_txn(stxn)
        assert "transaction rejected by ApprovalProgram" in e.message

    buyer_balance_after = algorand_helper.get_amount(buyer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    # Check tiquet is still in possession of buyer.
    assert algorand_helper.has_asset(buyer_account["pk"], tiquet_id)

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

    # Check buyer account balance is unchanged.
    assert buyer_balance_after == buyer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before
