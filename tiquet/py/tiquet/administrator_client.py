import base64

from tiquet.common import constants
from tiquet.common.algorand_helper import AlgorandHelper
from algosdk import encoding
from algosdk.future.transaction import (
    ApplicationCreateTxn,
    ApplicationNoOpTxn,
    AssetConfigTxn,
    LogicSigAccount,
    OnComplete,
    PaymentTxn,
    StateSchema,
)


class AdministratorClient:
    """
    Client for tiquet.io administrator.
    """

    def __init__(
        self,
        pk,
        sk,
        mnemonic,
        app_fpath,
        clear_fpath,
        algodclient,
        algod_params,
        logger,
    ):
        self.pk = pk
        self.sk = sk
        self.mnemonic = mnemonic
        self.app_fpath = app_fpath
        self.clear_fpath = clear_fpath
        self.algodclient = algodclient
        self.algod_params = algod_params
        self.logger = logger
        self.algorand_helper = AlgorandHelper(algodclient, logger)
        # TODO: Store in external persistent DB
        self.constants_app_id = None

    def deploy_constants_app(self):
        if self.constants_app_id:
            raise ValueError(
                "Constants App (Id: %d) already deployed." % self.constants_app_id
            )

        app_prog = self.algorand_helper.get_prog(self.app_fpath)
        clear_prog = self.algorand_helper.get_prog(self.clear_fpath)

        local_ints = 0
        local_bytes = 0
        global_ints = 2
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
        )

        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        ptx = self.algodclient.pending_transaction_info(txid)
        app_id = ptx["application-index"]

        self.logger.debug("Constants App Id: %d" % app_id)
        self.constants_app_id = app_id

        return app_id
