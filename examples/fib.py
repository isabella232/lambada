#!/usr/bin/env python3
#
# Compute-intensive fibonacci function to avoid coming near Lambda's 1mio free requests

import time
import math

level = 12 # 20 ca. 15s
counter = 0

def fib(x):
	global counter
	counter += 1
	for i in range(counter):
		a = math.sin(counter)
	if x in (1, 2):
		return 1
	return fib(x - 1) + fib(x - 2)

if __name__ == "__main__":
	starttime = time.time()
	print("fib(", level, ") =", fib(level))
	timedelta = time.time() - starttime
	print("time (ms)", round(timedelta * 1000, 2))
	print("calls", counter)
