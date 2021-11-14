import pytest
import uuid

from algosdk import encoding
from algosdk.error import AlgodHTTPError
from algosdk.future import transaction
from fixtures import *
from tiquet.common import constants
from tiquet.tiquet_issuer import TiquetIssuer


def test_issue_tiquet_success(
    tiquet_io_account,
    issuer_account,
    tiquet_price,
    tiquet_processing_fee_numerator,
    tiquet_processing_fee_denominator,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    administrator,
    tiquet_issuance_info,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    assert algorand_helper.created_app(issuer_account["pk"], app_id)

    expected_constants = {
        # Check tiquet.io processing fee global variables are set and assigned
        # the correct values.
        constants.TIQUET_PROCESSING_FEE_NUMERATOR_GLOBAL_VAR_NAME: {"value": tiquet_processing_fee_numerator},
        constants.TIQUET_PROCESSING_FEE_DENOMINATOR_GLOBAL_VAR_NAME: {"value": tiquet_processing_fee_denominator},
    }
    assert (
        algorand_helper.get_global_vars(administrator.constants_app_id, expected_constants.keys())
        == expected_constants
    )

    expected_app_global_vars = {
        # Check tiquet price global variable is set and is assigned the correct
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
        # Check tiquet for-sale flag global variable is set to true.
        constants.TIQUET_FOR_SALE_FLAG_GLOBAL_VAR_NAME: {"value": 1},
        # Check escrow address global variable is set and is assigned the
        # correct address.
        constants.TIQUET_ESCROW_ADDRESS_GLOBAL_VAR_NAME: {
            "value": escrow_lsig.address()
        },
    }
    assert (
        algorand_helper.get_global_vars(app_id, expected_app_global_vars.keys())
        == expected_app_global_vars
    )

def test_spoof_issue_tiquet_fail(
    tiquet_io_account,
    issuer_account,
    fraudster_account,
    tiquet_price,
    issuer_tiquet_royalty_frac,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    administrator,
    app_fpath,
    clear_fpath,
    escrow_fpath,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    issuer = TiquetIssuer(
        pk=issuer_account["pk"],
        sk=fraudster_account["sk"],
        mnemonic=fraudster_account["mnemonic"],
        app_fpath=app_fpath,
        clear_fpath=clear_fpath,
        escrow_fpath=escrow_fpath,
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
        tiquet_io_account=tiquet_io_account["pk"],
        constants_app_id=administrator.constants_app_id,
    )

    tiquet_name = uuid.uuid4()
    # TASA creation transaction will be rejected by the network.
    with pytest.raises(AlgodHTTPError) as e:
        issuer.issue_tiquet(tiquet_name, tiquet_price, issuer_tiquet_royalty_frac)
        # TODO(hv): Is this the right message we should be checking for?
        assert "transaction already in ledger" in e.message

def test_fraudster_updating_escrow_address_fail(
    tiquet_io_account,
    issuer_account,
    fraudster_account,
    tiquet_price,
    issuer_tiquet_royalty_numerator,
    issuer_tiquet_royalty_denominator,
    administrator,
    tiquet_issuance_info,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    # with open(success_teal_fpath, "rt") as f:
    #     fake_escrow_prog = base64.b64decode(algodclient.compile(f.read())["result"])
    # fake_escrow_lsig = transaction.LogicSigAccount(fake_escrow_prog)
    # fake_escrow_lsig_address = fake_escrow_lsig.address()

    tiquet_io_balance_before = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_before = algorand_helper.get_amount(issuer_account["pk"])
    fraudster_balance_before = algorand_helper.get_amount(fraudster_account["pk"])

    txn = transaction.ApplicationNoOpTxn(
        sender=fraudster_account["pk"],
        sp=algod_params,
        index=app_id,
        accounts=[issuer_account["pk"]],
        foreign_assets=[tiquet_id],
        app_args=["STORE_ESCROW_ADDRESS", encoding.decode_address(fraudster_account["pk"])],
    )
    stxn = txn.sign(fraudster_account["sk"])

    with pytest.raises(AlgodHTTPError) as e:
        algorand_helper.send_and_wait_for_txn(stxn)
        assert "transaction rejected by ApprovalProgram" in e.message

    tiquet_io_balance_after = algorand_helper.get_amount(tiquet_io_account["pk"])
    issuer_balance_after = algorand_helper.get_amount(issuer_account["pk"])
    fraudster_balance_after = algorand_helper.get_amount(fraudster_account["pk"])

    expected_global_vars = {
        # Check tiquet price global variable is set and is assigned the correct
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

    # Check tiquet.io account balance is unchanged.
    assert tiquet_io_balance_after == tiquet_io_balance_before
    # Check issuer account balance is unchanged.
    assert issuer_balance_after == issuer_balance_before
    # Check fraudster account balance is unchanged.
    assert fraudster_balance_after == fraudster_balance_before