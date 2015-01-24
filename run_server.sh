#!/bin/bash

SELF_DIR=$(dirname $(readlink -f $0))

source $SELF_DIR/aio/bin/activate
screen -AmdS market-rpg-club python $SELF_DIR/run.py
