#!/bin/bash

issuer_address=$(goal account list | awk '{print $2}' | tr " " "\n" | head -1)
echo "Issuer address: ${issuer_address}"

goal asset create \
  --creator $issuer_address \
  --name "Some Tiquet" \
  --asseturl "tiquet.io/sometiquet" \
  --assetmetadatab64 U29tZSBUaXF1ZXQ= \
  --unitname "TIQ" \
  --total 1 \
  --decimals 0