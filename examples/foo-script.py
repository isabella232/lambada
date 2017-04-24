import foo

if __name__ == "__main__":
	import sys
	sys.path.append("..")
	from lambadalib import functionproxy
	functionproxy.scan(globals())

	#foo.Foo = functionproxy.Proxy("foo.Foo")

f = foo.Foo()
print(f)
f.yell("first pass")
print(f.var)
f.yell("second pass")
print(f.var)
