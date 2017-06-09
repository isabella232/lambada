#!/usr/bin/env python3

import funcsplitter

fs = funcsplitter.FuncSplitter()
#fs.debug = True
fs.funcsplitter("functions", "insertionsort", ["[1, 9, 4, 2, 3]"])
fs.funcsplitter("functions", "countsort", ["[1, 9, 4, 2, 3]"])
