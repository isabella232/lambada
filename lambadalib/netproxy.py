# Lambada - Network proxy for classes

import json
import importlib

def color(s):
	return "\033[92m" + s + "\033[0m"

def Netproxy(d, classname, name, args):
	print(color("[netproxy] {} {} {} <{}>".format(classname, name, args, d)))
	if "." in classname:
		modname, classname = classname.split(".")
		#mod = __import__(modname)
		mod = importlib.import_module(modname)
		importlib.reload(mod)
		C = getattr(mod, classname)
	else:
		C = globals()[classname]
	_o = C()
	_o.__dict__ = json.loads(d)
	ret = getattr(_o, name)(*args)
	d = json.dumps(_o.__dict__)
	return d, ret
