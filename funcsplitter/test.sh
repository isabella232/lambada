#!/bin/sh

./funcsplitter.py $* functions.py somefunction 10
./funcsplitter.py $* --split-loops functions.py longloop
./funcsplitter.py $* --split-sleeps functions.py longsleep
