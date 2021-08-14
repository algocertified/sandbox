import pytest

from algosdk.error import AlgodHTTPError
from algosdk.future.transaction import AssetConfigTxn
from fixtures import *
from tiquet.tiquet_issuer import TiquetIssuer


def test_issue_tiquet_success(
    accounts, algodclient, algod_params, algorand_helper, logger
):
    # Get issuer algorand account, with public and secret keys.
    issuer_account = accounts.get_issuer_account()
    logger.debug("Issuer address: {}".format(issuer_account["pk"]))

    issuer = TiquetIssuer(
        pk=issuer_account["pk"],
        sk=issuer_account["sk"],
        mnemonic=issuer_account["mnemonic"],
        # TODO
        app_fpath="/root/tiquet/teal/tiquet_app.teal",
        clear_fpath="/root/tiquet/teal/clear.teal",
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
    )

    tiquet_id, app_id = issuer.issue_tiquet()

    assert algorand_helper.has_asset(issuer_account["pk"], tiquet_id)
    assert algorand_helper.created_app(issuer_account["pk"], app_id)


def test_spoof_issue_tiquet_fail(
    accounts, algodclient, algod_params, algorand_helper, logger
):
    # Get issuer's public key (Secret key is not available to anyone else,
    # inlcuding the fraudster).
    issuer_account = accounts.get_issuer_account()
    logger.debug("Issuer address: {}".format(issuer_account["pk"]))

    # Get fraudster algorand account, with public and secret keys.
    fraudster_account = accounts.get_fraudster_account()
    logger.debug("Fraudster address: {}".format(fraudster_account["pk"]))

    issuer = TiquetIssuer(
        pk=issuer_account["pk"],
        sk=fraudster_account["sk"],
        mnemonic=fraudster_account["mnemonic"],
        # TODO
        app_fpath="/root/tiquet/teal/tiquet_app.teal",
        clear_fpath="/root/tiquet/teal/clear.teal",
        algodclient=algodclient,
        algod_params=algod_params,
        logger=logger,
    )

    # TASA creation transaction will be rejected by the network.
    with pytest.raises(AlgodHTTPError) as e:
        issuer.issue_tiquet()
        # TODO(hv): Is this the right message we should be checking for?
        assert "transaction already in ledger" in e.message