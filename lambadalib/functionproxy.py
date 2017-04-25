# Lambada - Function proxy for classes

import json
import types

from lambadalib import netproxy

def color(s):
	return "\033[94m" + s + "\033[0m"

class Proxy:
	def __new__(cls, classname, proxy=True):
		print(color("[functionproxy new] {} {} {}".format(cls, classname, proxy)))
		if proxy:
			return lambda: Proxy(classname, False)
		else:
			return object.__new__(cls)

	#def __new__(cls, classname):
	#	print("//new", cls, classname)
	#	return object.__new__(cls)

	def __init__(self, classname, ignoreproxy):
		print(color("[functionproxy init] {}".format(classname)))
		self.classname = classname
		# rewritten constructor to support remote init
		self.__remote__init__()

	def __getattr__(self, name):
		print(color("[functionproxy remote call] {} {}".format(self.classname, name)))
		def method(*args):
			cn = self.classname
			_d = json.dumps(self.__dict__)
			_dc = json.loads(_d)
			del _dc["classname"]
			_d = json.dumps(_dc)
			print(color("[functionproxy] >> {} {}".format(args, _d)))
			_d, *args = netproxy.Netproxy(_d, self.classname, name, args)
			print(color("[functionproxy] << {} {}".format(args, _d)))
			self.__dict__ = json.loads(_d)
			self.__dict__["classname"] = cn
			return args
		return method

def scanclass(mod, modname, cname):
	print(color("[scan] class {} -> proxy".format(cname)))
	if mod and modname:
		setattr(mod, cname, Proxy("{}.{}".format(modname, cname)))
	else:
		globals()[cname] = Proxy("{}".format(cname))

def scan(globalnames):
	for modname in globalnames:
		if type(globalnames[modname]) == types.ModuleType:
			blacklist = ("json","sys","functionproxy")
			if modname not in ("__builtins__", __name__) + blacklist:
				print(color("[scan] module {}".format(modname)))
				mod = globalnames[modname]
				for cname in dir(mod):
					if getattr(mod, cname).__class__ == type:
						scanclass(mod, modname, cname)
		elif globalnames[modname].__class__ == type:
			pass
