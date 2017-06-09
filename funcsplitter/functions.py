def foo():
	pass

import math
def somefunction(n):
	n += 2
	z = n - 5
	z = math.sqrt(z)
	return z

def exchange(values, i, j):
	temp = values[i]
	values[i] = values[j]
	values[j] = temp

def insertionsort(numbers):
	for delimiter in range(1, len(numbers)):
		i = delimiter - 1
		while i >= 0 and numbers[i] > numbers[i+1]:
			exchange(numbers, i, i + 1)
			i -= 1
	return numbers

def countsort(numbers):
	counted = {}
	minnum = None
	maxnum = None
	for i, number in enumerate(numbers):
		if not number in counted:
			counted[number] = 0
		counted[number] += 1
		if minnum is None or number < minnum:
			minnum = number
		if maxnum is None or number > maxnum:
			maxnum = number
	numbers = []
	for i in range(minnum, maxnum + 1):
		if i in counted:
			val = counted[i]
			for j in range(val):
				numbers.append(i)
	return numbers

def longsleep():
	import time
	time.sleep(5)

def longloop():
	import math
	t = []
	c = 0
	for i in range(1000000):
		if i == 0:
			print("counter start", c)
		j = math.sin(i * math.sqrt(i) / (i + 1))
		t.append(math.cos(j))
		c += 1
	print("counter final", c)
