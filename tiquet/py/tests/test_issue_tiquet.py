import pytest
import uuid

from algosdk.error import AlgodHTTPError
from fixtures import *
from tiquet.tiquet_issuer import TiquetIssuer


def test_issue_tiquet_success(
    tiquet_io_account,
    issuer_account,
    tiquet_issuance_info,
    algodclient,
    algod_params,
    algorand_helper,
    logger,
):
    tiquet_id, app_id, escrow_lsig = tiquet_issuance_info

    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    assert algorand_helper.created_app(issuer_account["pk"], app_id)


def test_spoof_issue_tiquet_fail(
    tiquet_io_account,
    issuer_account,
    fraudster_account,
    tiquet_price,
    app_fpath,
    clear_fpath,
    escrow_fpath,
    algodclient,
    algod_params,
    algorand_helper,
    logger
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
    )

    tiquet_name = uuid.uuid4()
    # TASA creation transaction will be rejected by the network.
    with pytest.raises(AlgodHTTPError) as e:
        issuer.issue_tiquet(tiquet_name, tiquet_price)
        # TODO(hv): Is this the right message we should be checking for?
        assert "transaction already in ledger" in e.message
