import base64
import json

from algosdk import encoding

# Methods copied from https://github.com/algorand/docs/blob/master/examples/assets/v2/python/asset_example.py.
class AlgorandHelper:
    def __init__(self, algodclient, logger):
        self.client = algodclient
        self.logger = logger

    # Utility function to send a transaction and wait until the transaction is confirmed.
    def send_and_wait_for_txn(self, stxn):
        txid = self.client.send_transaction(stxn)
        self.logger.debug("Txn Id: {}".format(txid))
        self.wait_for_confirmation(txid)
        return txid

    def wait_for_confirmation(self, txid):
        """
        Utility function to wait until the transaction is
        confirmed before proceeding.
        """
        last_round = self.client.status().get("last-round")
        txinfo = self.client.pending_transaction_info(txid)
        while not (txinfo.get("confirmed-round") and txinfo.get("confirmed-round") > 0):
            self.logger.debug("Waiting for confirmation")
            last_round += 1
            self.client.status_after_block(last_round)
            txinfo = self.client.pending_transaction_info(txid)
        self.logger.debug(
            "Transaction {} confirmed in round {}".format(
                txid, txinfo.get("confirmed-round")
            )
        )
        return txinfo

    def created_app(self, account, app_id):
        account_info = self.client.account_info(account)
        return any(app["id"] == app_id for app in account_info["created-apps"])

    def get_global_vars(self, app_id, global_var_names):
        application_info = self.client.application_info(app_id)
        if "global-state" not in application_info["params"]:
            raise ValueError("App %d has no global state" % app_id)

        var_keys = {}
        for var_name in global_var_names:
            key = str(base64.b64encode(var_name.encode("ascii")))[2:-1]
            var_keys[key] = var_name

        out_global_vars = {}
        for global_var in application_info["params"]["global-state"]:
            if global_var["key"] in var_keys:
                var_name = var_keys[global_var["key"]]
                out_global_vars[var_name] = {}

                if global_var["value"]["type"] == 1:
                    out_global_vars[var_name]["value"] = global_var["value"]["bytes"]
                    addr_value = encoding.encode_address(
                        base64.b64decode(out_global_vars[var_name]["value"])
                    )
                    if encoding.is_valid_address(addr_value):
                        out_global_vars[var_name]["value"] = addr_value
                elif global_var["value"]["type"] == 2:
                    out_global_vars[var_name]["value"] = global_var["value"]["uint"]
                else:
                    raise ValueError(
                        "Stored global variable %s has unrecognized type: %s"
                        % (var_name, str(global_var["value"]["type"]))
                    )

        return out_global_vars

    def has_asset(self, account, assetid, amount=1):
        account_info = self.client.account_info(account)
        return all(
            asset["amount"] == amount
            for asset in account_info["assets"]
            if asset["asset-id"] == assetid
        )

    def get_amount(self, account):
        account_info = self.client.account_info(account)
        return account_info["amount"]

    # Utility function used to print created asset for account and assetid
    def log_created_asset(self, account, assetid):
        # note: if you have an indexer instance available it is easier to just use this
        # response = myindexer.accounts(asset_id = assetid)
        # then use 'account_info['created-assets'][0] to get info on the created asset
        account_info = self.client.account_info(account)
        idx = 0
        for my_account_info in account_info["created-assets"]:
            scrutinized_asset = account_info["created-assets"][idx]
            idx = idx + 1
            if scrutinized_asset["index"] == assetid:
                self.logger.debug("Asset Id: {}".format(scrutinized_asset["index"]))
                self.logger.debug(json.dumps(my_account_info["params"], indent=4))
                break

    # Utility function used to print asset holding for account and assetid
    def log_asset_holding(self, account, assetid):
        # note: if you have an indexer instance available it is easier to just use this
        # response = myindexer.accounts(asset_id = assetid)
        # then loop thru the accounts returned and match the account you are looking for
        account_info = self.client.account_info(account)
        idx = 0
        for my_account_info in account_info["assets"]:
            scrutinized_asset = account_info["assets"][idx]
            idx = idx + 1
            if scrutinized_asset["asset-id"] == assetid:
                self.logger.debug("Asset Id: {}".format(scrutinized_asset["asset-id"]))
                self.logger.debug(json.dumps(scrutinized_asset, indent=4))
                break
