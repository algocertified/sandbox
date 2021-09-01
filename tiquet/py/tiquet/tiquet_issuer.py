import base64

from tiquet.common import constants
from tiquet.common.algorand_helper import AlgorandHelper
from algosdk.future.transaction import (
    ApplicationCreateTxn,
    ApplicationNoOpTxn,
    AssetConfigTxn,
    LogicSigAccount,
    OnComplete,
    PaymentTxn,
    StateSchema,
)


class TiquetIssuer:
    """
    Represents a tiquet issuer.
    """

    _ESCROW_DEPOSIT_AMT = 1000000

    def __init__(
        self,
        pk,
        sk,
        mnemonic,
        app_fpath,
        clear_fpath,
        escrow_fpath,
        algodclient,
        algod_params,
        logger,
        tiquet_io_account,
    ):
        self.pk = pk
        self.sk = sk
        self.mnemonic = mnemonic
        self.app_fpath = app_fpath
        self.clear_fpath = clear_fpath
        self.escrow_fpath = escrow_fpath
        self.algodclient = algodclient
        self.algod_params = algod_params
        self.logger = logger
        self.tiquet_io_account = tiquet_io_account
        self.algorand_helper = AlgorandHelper(algodclient, logger)

    def issue_tiquet(self, name, price):
        tiquet_id = self._create_tasa(name)
        app_id = self._deploy_tiquet_app(tiquet_id, price)
        escrow_lsig = self._deploy_tiquet_escrow(app_id, tiquet_id)
        escrow_address = escrow_lsig.address()
        self._set_tiquet_clawback(tiquet_id, escrow_address)
        self._fund_escrow(escrow_address)
        self._store_escrow_address(app_id, tiquet_id, escrow_address)
        return (tiquet_id, app_id, escrow_lsig)

    def _create_tasa(self, name):
        txn = AssetConfigTxn(
            sender=self.pk,
            sp=self.algod_params,
            total=1,
            default_frozen=False,
            asset_name="tiquet",
            manager=self.pk,
            reserve=self.pk,
            freeze=self.pk,
            clawback=self.pk,
            url="https://tiquet.io/tiquet/%s" % name,
            decimals=0,
        )

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)

        ptx = self.algodclient.pending_transaction_info(txid)
        tasa_id = ptx["asset-index"]
        self.algorand_helper.log_created_asset(self.pk, tasa_id)
        self.algorand_helper.log_asset_holding(self.pk, tasa_id)

        return tasa_id

    def _deploy_tiquet_app(self, tasa_id, price):
        var_assigns = {
            "TIQUET_PRICE": price,
            "TIQUET_ID": tasa_id,
            "ISSUER_ADDRESS": self.pk,
        }
        app_prog = self._get_prog(self.app_fpath, var_assigns=var_assigns)
        clear_prog = self._get_prog(self.clear_fpath)

        self.logger.debug("app_prog: " + str(app_prog))

        local_ints = 0
        local_bytes = 0
        global_ints = 1
        global_bytes = 1
        global_schema = StateSchema(global_ints, global_bytes)
        local_schema = StateSchema(local_ints, local_bytes)

        txn = ApplicationCreateTxn(
            sender=self.pk,
            sp=self.algod_params,
            on_complete=OnComplete.NoOpOC,
            approval_program=app_prog,
            clear_program=clear_prog,
            global_schema=global_schema,
            local_schema=local_schema,
            foreign_assets=[tasa_id],
        )

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        ptx = self.algodclient.pending_transaction_info(txid)
        app_id = ptx["application-index"]

        # TODO(hv): Add logging statements

        return app_id

    def _deploy_tiquet_escrow(self, app_id, tasa_id):
        var_assigns = {
            "TIQUET_APP_ID": app_id,
            "TIQUET_ID": tasa_id,
            "TIQUET_IO_PROCESSING_FEE": constants.TIQUET_IO_PROCESSING_FEE,
            "TIQUET_IO_ADDRESS": self.tiquet_io_account,
            "ISSUER_ADDRESS": self.pk,
        }
        escrow_prog = self._get_prog(self.escrow_fpath, var_assigns=var_assigns)
        return LogicSigAccount(escrow_prog)

    def _set_tiquet_clawback(self, tiquet_id, escrow_address):
        txn = AssetConfigTxn(
            sender=self.pk,
            sp=self.algod_params,
            index=tiquet_id,
            total=1,
            manager=self.pk,
            reserve=self.pk,
            freeze=self.pk,
            clawback=escrow_address,
        )

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)

    def _fund_escrow(self, escrow_address):
        txn = PaymentTxn(
            sender=self.pk,
            sp=self.algod_params,
            receiver=escrow_address,
            amt=self._ESCROW_DEPOSIT_AMT,
        )

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)

    def _store_escrow_address(self, app_id, tiquet_id, escrow_address):
        txn = ApplicationNoOpTxn(
            sender=self.pk,
            sp=self.algod_params,
            index=app_id,
            accounts=[self.pk],
            foreign_assets=[tiquet_id],
            app_args=[escrow_address],
        )
        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)

    def _get_prog(self, fpath, var_assigns={}):
        with open(fpath, "rt") as f:
            source = f.read()
            for var, value in var_assigns.items():
                source = source.replace("{{%s}}" % var, str(value))
            return base64.b64decode(self.algodclient.compile(source)["result"])
