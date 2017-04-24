class Foo:
	def __init__(self):
		self.__remote__init__()

	def __remote__init__(self):
		self.var = 99

	def yell(self, s):
		print("Yell!", s)
		self.var += 1
