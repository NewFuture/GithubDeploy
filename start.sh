#!/usr/bin/env bash

cd "$(dirname "${BASH_SOURCE[0]}")";

nohup /usr/bin/python ./GitAutoDeploy.py -q > error.log 2>&1 &
