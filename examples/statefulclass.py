class StatefulClass:
	def __init__(self):
		self.counter = 0

	def increment(self):
		self.counter += 1

if __name__ == "__main__":
	sc = StatefulClass()
	sc.increment()
	sc.increment()
	print(sc.counter)
