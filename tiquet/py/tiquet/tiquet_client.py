from algosdk.future import transaction
from tiquet.common.algorand_helper import AlgorandHelper


class TiquetClient:
    """
    Client for individuals to interact with tiquet marketplace.
    """

    def __init__(
        self,
        pk,
        sk,
        mnemonic,
        algodclient,
        algod_params,
        logger,
        escrow_lsig,
    ):
        self.pk = pk
        self.sk = sk
        self.mnemonic = mnemonic
        self.algodclient = algodclient
        self.algod_params = algod_params
        self.logger = logger
        self.escrow_lsig = escrow_lsig
        self.algorand_helper = AlgorandHelper(algodclient, logger)

    def buy_tiquet(self, tiquet_id, app_id, issuer_account, seller_account, amount):
        self._tiquet_opt_in(tiquet_id)

        txn1 = transaction.ApplicationNoOpTxn(
            sender=self.pk,
            sp=self.algod_params,
            index=app_id,
            accounts=[issuer_account],
            foreign_assets=[tiquet_id],
        )

        txn2 = transaction.AssetTransferTxn(
            sender=self.escrow_lsig.address(),
            sp=self.algod_params,
            receiver=self.pk,
            amt=1,
            index=tiquet_id,
            revocation_target=seller_account,
        )

        txn3 = transaction.PaymentTxn(
            sender=self.pk,
            sp=self.algod_params,
            receiver=seller_account,
            amt=amount,
        )

        gid = transaction.calculate_group_id([txn1, txn2, txn3])
        txn1.group = gid
        txn2.group = gid
        txn3.group = gid

        stxn1 = txn1.sign(self.sk)
        stxn2 = transaction.LogicSigTransaction(txn2, self.escrow_lsig)
        assert stxn2.verify()
        stxn3 = txn3.sign(self.sk)

        txid = self.algodclient.send_transactions([stxn1, stxn2, stxn3])

        self.algorand_helper.wait_for_confirmation(txid)

        return self.algodclient.pending_transaction_info(txid)
        
    def _tiquet_opt_in(self, tiquet_id):
        txn = transaction.AssetOptInTxn(
            sender=self.pk,
            sp=self.algod_params,
            index=tiquet_id,
        )
        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)
