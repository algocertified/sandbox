FROM sandbox_algod:latest

ARG MNEMONICS_FILE=/tmp/config/mnemonics_privnet.txt

WORKDIR /root/tiquet
COPY ./tiquet /root/tiquet
COPY ./config/mnemonics_testnet.txt /tmp/config/mnemonics_testnet.txt

RUN apt update
RUN apt install python3 -y
RUN apt install python3-pip -y
RUN apt install libffi-dev
RUN python3 -m pip install black py-algorand-sdk pytest

COPY images/tiquet/get_privnet_mnemonics.sh /tmp/get_privnet_mnemonics.sh
RUN /tmp/get_privnet_mnemonics.sh

RUN python3 -m pip install /root/tiquet/py