#!/usr/bin/env python

import unittest
from myapp import complextrig, calculate, calculatecsv

class TestMyApp(unittest.TestCase):
	def testmyapp(self):
		epsilon = 0.01
		self.assertTrue(complextrig(1.0) - 1.381 < epsilon)
		self.assertTrue(calculate([1.0, 2.0]) - 1.874 < epsilon)
		self.assertTrue(calculatecsv() - 1.874 < epsilon)

unittest.main()
