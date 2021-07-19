#!/bin/bash

issuer_address=$(goal account list | awk '{print $2}' | tr " " "\n" | head -1)
echo "Issuer address: ${issuer_address}"

approval_prog="teal/tiquet_app.teal"
clear_prog="teal/clear.teal"

global_byteslices=0
global_ints=1
local_byteslices=0
local_ints=0

asa_id=1

goal app create \
    --creator $issuer_address \
    --approval-prog $approval_prog \
    --clear-prog $clear_prog \
    --global-byteslices $global_byteslices \
    --global-ints $global_ints \
    --local-byteslices $local_byteslices \
    --local-ints $local_ints \
    --foreign-asset $asa_id
