#!/usr/bin/env python3

import math
import csv

import lambada

def complextrig(v):
	return math.sin(v) + math.cos(v)

def calculate(values):
	return sum(map(complextrig, values))

def calculatecsv():
	values = []
	print("intrusive lambda stdout message!")
	with open("values.csv") as f:
		reader = csv.reader(f)
		for row in reader:
			values.append(int(row[1]))
	return calculate(values)

if __name__ == "__main__":
	lambada.move(globals())
	print(calculate([98, 99, 100]))
	print(calculatecsv())
