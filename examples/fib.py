#!/usr/bin/env python3
#
# Standard fibonacci function

import time
import math

level = 40 # 20 ca. 2ms, 30 ca. 190ms (with pypy3: 55ms)

def fib(x):
	if x in (1, 2):
		return 1
	return fib(x - 1) + fib(x - 2)

if __name__ == "__main__":
	deltas = []
	for i in range(100):
		starttime = time.time()
		print("fib(", level, ") =", fib(level))
		timedelta = round((time.time() - starttime) * 1000, 2)
		print("time (ms)", timedelta)
		deltas.append(timedelta)
	print("overall time: ", sum(deltas) / len(deltas))
