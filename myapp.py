#!/usr/bin/env python3

import math
import csv

import sys
if sys.version_info.major == 3:
	import lambada

def complextrig(v):
	print("// complextrig", v)
	return math.sin(v) + math.cos(v)

def calculate(values):
	return sum(map(complextrig, values))

def calculatecsv():
	values = []
	input("confirm CSV input?") # force tainting
	print("intrusive lambda stdout message!")
	with open("values.csv") as f: # issue with codegen
	#f = open("values.csv")
	#if 1 == 1:
		reader = csv.reader(f)
		for row in reader:
			values.append(int(row[1]))
	return calculate(values)

if __name__ == "__main__":
	if sys.version_info.major == 3:
		lambada.move(globals())
		print(calculate([98, 99, 100]))
		print(calculatecsv())
	else:
		raise Exception("Dynamic lambdafication requires Python 3.")
