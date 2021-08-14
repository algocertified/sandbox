#!/bin/bash

if command -v ./sandbox &> /dev/null
then
  GOAL_COMMAND="./sandbox goal"
else
  GOAL_COMMAND="goal"
fi

issuer_address=$(${GOAL_COMMAND} account list | awk '{print $2}' | tr " " "\n" | sed -n 1p)
echo "Issuer address: ${issuer_address}"
buyer_address=$(${GOAL_COMMAND} account list | awk '{print $2}' | tr " " "\n" | sed -n 2p)
echo "Buyer address: ${buyer_address}"

app_id=2
asa_id=1
purchase_amt=100

${GOAL_COMMAND} app call \
    --app-id ${app_id} \
    -f ${buyer_address} \
    --app-account ${issuer_address} \
    --foreign-asset ${asa_id} \
    -o app_call.txn

${GOAL_COMMAND} clerk send \
    -f ${buyer_address} \
    -t ${issuer_address} \
    -a ${purchase_amt} \
    -o purchase.txn

${GOAL_COMMAND} clerk sign -i app_call.txn -o app_call.stxn
${GOAL_COMMAND} clerk sign -i purchase.txn -o purchase.stxn

cat app_call.stxn purchase.stxn > group.sgtxn
${GOAL_COMMAND} clerk rawsend -f group.sgtxn