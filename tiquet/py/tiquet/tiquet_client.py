from algosdk.future import transaction
from tiquet.common import constants
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
        tiquet_io_account,
        constants_app_id,
    ):
        self.pk = pk
        self.sk = sk
        self.mnemonic = mnemonic
        self.algodclient = algodclient
        self.algod_params = algod_params
        self.logger = logger
        self.tiquet_io_account = tiquet_io_account
        self.constants_app_id = constants_app_id
        self.algorand_helper = AlgorandHelper(algodclient, logger)

    def buy_tiquet(
        self, tiquet_id, app_id, escrow_lsig, issuer_account, seller_account, amount
    ):
        self.tiquet_opt_in(tiquet_id)

        is_resale = issuer_account != seller_account
        global_vars = self._get_global_vars(app_id)

        if is_resale:
            app_command_name = constants.TIQUET_APP_RESALE_COMMAND
        else:
            app_command_name = constants.TIQUET_APP_INITIAL_SALE_COMMAND

        # Application call to execute sale.
        txn1 = transaction.ApplicationNoOpTxn(
            sender=self.pk,
            sp=self.algod_params,
            index=app_id,
            accounts=[issuer_account, seller_account],
            foreign_apps=[self.constants_app_id],
            foreign_assets=[tiquet_id],
            app_args=[app_command_name],
        )

        # Tiquet transfer to buyer.
        txn2 = transaction.AssetTransferTxn(
            sender=escrow_lsig.address(),
            sp=self.algod_params,
            receiver=self.pk,
            amt=1,
            index=tiquet_id,
            revocation_target=seller_account,
        )

        # Tiquet payment to seller.
        txn3 = transaction.PaymentTxn(
            sender=self.pk,
            sp=self.algod_params,
            receiver=seller_account,
            amt=amount,
        )

        # Processing fee to tiquet.io.
        txn4 = transaction.PaymentTxn(
            sender=self.pk,
            sp=self.algod_params,
            receiver=self.tiquet_io_account,
            amt=self._get_processing_fee(global_vars),
        )

        if is_resale:
            # Royalty fee to issuer.
            txn5 = transaction.PaymentTxn(
                sender=self.pk,
                sp=self.algod_params,
                receiver=issuer_account,
                amt=self._get_tiquet_royalty_amount(global_vars),
            )

        txns = [txn1, txn2, txn3, txn4]
        if is_resale:
            txns.append(txn5)

        gid = transaction.calculate_group_id(txns)
        txn1.group = gid
        txn2.group = gid
        txn3.group = gid
        txn4.group = gid
        if is_resale:
            txn5.group = gid

        stxn1 = txn1.sign(self.sk)
        stxn2 = transaction.LogicSigTransaction(txn2, escrow_lsig)
        assert stxn2.verify()
        stxn3 = txn3.sign(self.sk)
        stxn4 = txn4.sign(self.sk)
        stxns = [stxn1, stxn2, stxn3, stxn4]
        if is_resale:
            stxn5 = txn5.sign(self.sk)
            stxns.append(stxn5)

        txid = self.algodclient.send_transactions(stxns)

        self.algorand_helper.wait_for_confirmation(txid)

        return self.algodclient.pending_transaction_info(txid)

    def tiquet_opt_in(self, tiquet_id):
        txn = transaction.AssetOptInTxn(
            sender=self.pk,
            sp=self.algod_params,
            index=tiquet_id,
        )
        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)

    def post_for_resale(self, tiquet_id, app_id, tiquet_price):
        txn = transaction.ApplicationNoOpTxn(
            sender=self.pk,
            sp=self.algod_params,
            index=app_id,
            accounts=[self.pk],
            foreign_assets=[tiquet_id],
            app_args=[constants.TIQUET_APP_POST_FOR_RESALE_COMMAND, tiquet_price],
        )
        stxn = txn.sign(self.sk)
        txid = self.algorand_helper.send_and_wait_for_txn(stxn)
        return self.algodclient.pending_transaction_info(txid)

    def _get_global_vars(self, app_id):
        global_vars = self.algorand_helper.get_global_vars(
            app_id,
            [
                constants.TIQUET_PRICE_GLOBAL_VAR_NAME,
                constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME,
                constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME,
            ],
        )
        constant_global_vars = self.algorand_helper.get_global_vars(
            self.constants_app_id,
            [
                constants.TIQUET_PROCESSING_FEE_NUMERATOR_GLOBAL_VAR_NAME,
                constants.TIQUET_PROCESSING_FEE_DENOMINATOR_GLOBAL_VAR_NAME,
            ],
        )
        global_vars.update(constant_global_vars)
        return global_vars

    def _get_processing_fee(self, global_vars):
        tiquet_price = global_vars[constants.TIQUET_PRICE_GLOBAL_VAR_NAME]["value"]
        processing_fee_numerator = global_vars[
            constants.TIQUET_PROCESSING_FEE_NUMERATOR_GLOBAL_VAR_NAME
        ]["value"]
        processing_fee_denominator = global_vars[
            constants.TIQUET_PROCESSING_FEE_DENOMINATOR_GLOBAL_VAR_NAME
        ]["value"]
        return int(
            (processing_fee_numerator / processing_fee_denominator) * tiquet_price
        )

    def _get_tiquet_royalty_amount(self, global_vars):
        tiquet_price = global_vars[constants.TIQUET_PRICE_GLOBAL_VAR_NAME]["value"]
        royalty_numerator = global_vars[
            constants.TIQUET_ISSUER_ROYALTY_NUMERATOR_GLOBAL_VAR_NAME
        ]["value"]
        royalty_denominator = global_vars[
            constants.TIQUET_ISSUER_ROYALTY_DENOMINATOR_GLOBAL_VAR_NAME
        ]["value"]
        return int((royalty_numerator / royalty_denominator) * tiquet_price)
