# DECORATORS
# Copy one of the two decorator definitions into your code

# Simple decorator with attributes
def cloudfunction(f): return f

# Flexible decorator with attributes
# Lambada recognised 'memory' and 'runtime'
def cloudfunction(**kwargs):
	def real_cloudfunction(f):
		def wrapper(*args, **kwargs):
			return f(*args, **kwargs)
		return wrapper
	return real_cloudfunction

# EXAMPLE
# Do not copy the code below but be inspired by it...

@cloudfunction(memory=256, region="us-west-1")
def testfunction(x):
	return x+1

# FIXME: currently Lambada requires the guard
if __name__ == "__main__":
	print(testfunction(9))
