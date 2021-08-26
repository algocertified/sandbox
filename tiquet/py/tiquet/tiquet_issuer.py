import base64

from tiquet.common.algorand_helper import AlgorandHelper
from algosdk.future.transaction import (
    ApplicationCreateTxn,
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

    ESCROW_DEPOSIT_AMT=1000000

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
        self.algorand_helper = AlgorandHelper(algodclient, logger)

    def issue_tiquet(self):
        tiquet_id = self._create_tasa()
        app_id = self._deploy_tiquet_app(tiquet_id)
        escrow_lsig = self._deploy_tiquet_escrow()
        escrow_address = escrow_lsig.address()
        self._set_tiquet_clawback(tiquet_id, escrow_address)
        self._fund_escrow(escrow_address)
        return (tiquet_id, app_id, escrow_lsig)

    def _create_tasa(self):
        txn = AssetConfigTxn(
            sender=self.pk,
            sp=self.algod_params,
            total=1,
            default_frozen=False,
            unit_name="Tiquet",
            asset_name="tiquet",
            manager=self.pk,
            reserve=self.pk,
            freeze=self.pk,
            clawback=self.pk,
            url="https://tiquet.io/tiquet",
            decimals=0,
        )

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)

        ptx = self.algodclient.pending_transaction_info(txid)
        tasa_id = ptx["asset-index"]
        self.algorand_helper.log_created_asset(self.pk, tasa_id)
        self.algorand_helper.log_asset_holding(self.pk, tasa_id)

        return tasa_id

    def _deploy_tiquet_app(self, tasa_id):
        app_prog = self._get_prog(self.app_fpath)
        clear_prog = self._get_prog(self.clear_fpath)

        self.logger.debug("app_prog: " + str(app_prog))

        local_ints = 0
        local_bytes = 0
        global_ints = 1
        global_bytes = 0
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

    def _deploy_tiquet_escrow(self):
        escrow_prog = self._get_prog(self.escrow_fpath)
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
            clawback=escrow_address)

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)

    def _fund_escrow(self, escrow_address):
        txn = PaymentTxn(
            sender=self.pk,
            sp=self.algod_params,
            receiver=escrow_address,
            amt=self.ESCROW_DEPOSIT_AMT,
        )

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)

    def _get_prog(self, fpath):
        with open(fpath, "rt") as f:
            source = f.read()
            return base64.b64decode(self.algodclient.compile(source)["result"])
