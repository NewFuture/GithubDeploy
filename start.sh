#!/bin/sh
nohup /usr/bin/python ./GitAutoDeploy.py -q > error.log 2>&1 &
