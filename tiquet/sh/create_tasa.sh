#!/bin/bash

if command -v ./sandbox &> /dev/null
then
  GOAL_COMMAND="./sandbox goal"
else
  GOAL_COMMAND="goal"
fi

issuer_address=$(${GOAL_COMMAND} account list | awk '{print $2}' | tr " " "\n" | head -1)
echo "Issuer address: ${issuer_address}"

${GOAL_COMMAND} asset create \
  --creator $issuer_address \
  --name "Some Tiquet" \
  --asseturl "tiquet.io/sometiquet" \
  --assetmetadatab64 U29tZSBUaXF1ZXQ= \
  --unitname "TIQ" \
  --total 1 \
  --decimals 0