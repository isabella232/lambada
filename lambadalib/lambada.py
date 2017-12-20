# Lambada - Main module

import inspect
import ast
#import astor.codegen as codegen
import tempfile
import zipfile
import subprocess
import time
import os

from lambadalib import codegen
from lambadalib import functionproxy

def printlambada(*s):
	red = "\033[1;31m"
	reset = "\033[0;0m"
	s += (reset,)
	print(red, "»» Lambada:", *s)

def lambadamonad(s):
	green = "\033[1;32m"
	reset = "\033[0;0m"
	print(green, "»» Lambada Monad:", s, reset)

class CloudFunctionConfiguration:
	def __init__(self):
		self.enabled = False
		self.memory = None
		self.duration = None
		self.region = None

	def __str__(self):
		return "CFC({}|{}|{})".format(self.memory, self.duration, self.region)

	def __format__(self, s):
		return self.__str__()

class FuncListener(ast.NodeVisitor):
	def __init__(self, functionname, functions, annotations):
		ast.NodeVisitor.__init__(self)
		self.functionname = functionname
		self.functions = functions
		self.annotations = annotations
		self.currentfunction = None
		self.tainted = []
		self.filtered = []
		self.args = {}
		self.bodies = {}
		self.deps = {}
		self.features = {}
		self.classes = {}
		self.cfcs = {}

	def checkdep(self, dep):
		if dep in self.functions and not dep in self.deps.get(self.currentfunction, []):
			printlambada("AST: dependency {:s} -> {:s}".format(self.currentfunction, dep))
			self.deps.setdefault(self.currentfunction, []).append(dep)

	def visit_ClassDef(self, node):
		#print("AST: class def", node.body)
		self.classes[node.name] = node

	def visit_Call(self, node):
		#print("AST: call", node.func)
		if "id" in dir(node.func):
			#print("AST: direct-dependency-call", node.func.id, "@", self.currentfunction)
			self.checkdep(node.func.id)
		for arg in node.args:
			if isinstance(arg, ast.Call):
				#print("AST: indirect-dependency-call", arg.func.id)
				if not "id" in dir(arg.func):
					# corner cases
					continue
				self.checkdep(arg.func.id)
				if arg.func.id == "map":
					for maparg in arg.args:
						if isinstance(maparg, ast.Name):
							#print("AST: map-call", maparg.id)
							self.checkdep(maparg.id)

	def visit_Return(self, node):
		#printlambada("ASTRET:", node.value)
		#a = ast.Assign([ast.Name("ret", ast.Store())], node.value)
		#r = ast.Return(ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambdalog", ast.Load())]))
		d = ast.Dict([ast.Str("ret"), ast.Str("log")], [node.value, ast.Name("__lambdalog", ast.Load())])
		#b = ast.Assign([ast.Name("ret", ast.Store())], d)
		#r = ast.Return(ast.Name("ret", ast.Load()))
		#g = ast.Global(["__lambdalog"])
		#z = ast.Assign([ast.Name("__lambdalog", ast.Store())], ast.Str(""))
		#newbody = [g] + newbody + [a, b, z, r]
		node.value = d

	def visit_FunctionDef(self, node):
		#printlambada("AST:", node.name, node.args)
		#printlambada("AST:", node.args.args[0].arg)
		self.currentfunction = node.name

		if self.annotations:
			if node.name == "cloudfunction":
				self.generic_visit(node)
				#return
			cfc = CloudFunctionConfiguration()
			for name in node.decorator_list:
				if "id" in dir(name):
					if name.id == "cloudfunction":
						cfc.enabled = True
				else:
					if name.func.id == "cloudfunction":
						cfc.enabled = True
						for keyword in name.keywords:
							if keyword.arg == "memory":
								cfc.memory = keyword.value.n
							elif keyword.arg == "region":
								cfc.region = keyword.value.s
							elif keyword.arg == "duration":
								cfc.duration = keyword.value.n
			if cfc.enabled:
				printlambada("AST: annotation {:s} @ {:s}".format(cfc, node.name))
				self.cfcs[node.name] = cfc
			else:
				printlambada("AST: no annotation @ {:s}".format(node.name))
				self.generic_visit(node)
				#return
				self.filtered.append(node.name)

		if self.functionname == None or node.name == self.functionname:
			#printlambada("AST: hit function!")
			#printlambada(dir(node))
			for arg in node.args.args:
				#printlambada("AST: argument", arg.arg)
				pass
			for linekind in node.body:
				#printlambada("AST: linekind", linekind, dir(linekind))
				if isinstance(linekind, ast.Expr):
					#printlambada("AST: match", linekind.value, linekind.value.func.id)
					if not "func" in dir(linekind.value) or not "id" in dir(linekind.value.func):
						# corner cases
						continue
					if linekind.value.func.id in ("input",):
						self.tainted.append(node.name)
					elif linekind.value.func.id in ("print",):
						self.features.setdefault(node.name, []).append("print")
		if not node.name in self.tainted:
			for arg in node.args.args:
				self.args.setdefault(node.name, []).append(arg.arg)
			#print("-----8<-----")
			#print(dir(node))
			#print(ast.dump(node, annotate_fields=False))
			newbody = []
			for linekind in node.body:
				if isinstance(linekind, ast.Return):
					a = ast.Assign([ast.Name("ret", ast.Store())], linekind.value)
					#r = ast.Return(ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambdalog", ast.Load())]))
					d = ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambdalog", ast.Load())])
					b = ast.Assign([ast.Name("ret", ast.Store())], d)
					r = ast.Return(ast.Name("ret", ast.Load()))
					g = ast.Global(["__lambdalog"])
					z = ast.Assign([ast.Name("__lambdalog", ast.Store())], ast.Str(""))

					# FIXME: always assume log because here the monadic situation through dependencies is not yet clear
					#if "print" in self.features.get(node.name, []):
					#	r = ast.Return(ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambdalog", ast.Load())]))
					#else:
					#	r = ast.Return(ast.Dict([ast.Str("ret")], [ast.Name("ret", ast.Load())]))
					#print("//return", linekind.value)
					#print(ast.dump(a, annotate_fields=False))
					#print(ast.dump(r, annotate_fields=False))
					newbody = [g] + newbody + [a, b, z, r]
					#Assign([Name('ret', Store())], ...)
					#Return(Name('ret', Load()))
				else:
					newbody.append(linekind)
					#print(ast.dump(linekind, annotate_fields=False))
			#for linekind in newbody:
			#	print(ast.dump(linekind, annotate_fields=False))
			#print("-----8<-----")
			self.bodies[node.name] = newbody
		self.generic_visit(node)

def analyse(functionname, functions, module, annotations):
	if not module:
		modulename = inspect.stack()[-1][1]
		printlambada("targeting", modulename, "...")
	else:
		modulename = module

	modulestring = open(modulename).read()
	tree = ast.parse(modulestring, modulename)
	fl = FuncListener(functionname, functions, annotations)
	fl.visit(tree)
	for function in functions:
		for dep in fl.deps.get(function, []):
			if dep in fl.tainted:
				printlambada("AST: dependency {:s} -> {:s} leads to tainting".format(function, dep))
				fl.tainted.append(function)
	for function in functions:
		for dep in fl.deps.get(function, []):
			if dep in fl.filtered:
				taint = True
				#if dep not in fl.tainted:
				#	printlambada("AST: dependency {:s} -> {:s} leads to unfiltering".format(function, dep))
				#	taint = False
				if taint:
					fl.tainted.append(dep)
	return fl.tainted, fl.args, fl.bodies, fl.deps, fl.features, fl.classes, fl.cfcs

def awstool(endpoint):
	if endpoint:
		return "aws --endpoint-url {:s}".format(endpoint)
	else:
		return "aws"

template = """
def FUNCNAME_remote(event, context):
	UNPACKPARAMETERS
	FUNCTIONIMPLEMENTATION

def FUNCNAME_stub(jsoninput):
	event = json.loads(jsoninput)
	ret = FUNCNAME_remote(event, None)
	return json.dumps(ret)

def FUNCNAME(PARAMETERSHEAD):
	local = LOCAL
	jsoninput = json.dumps(PACKEDPARAMETERS)
	if local:
		jsonoutput = FUNCNAME_stub(jsoninput)
	else:
		functionname = "FUNCNAME_lambda"
		runcode = [AWSTOOL, "lambda", "invoke", "--function-name", functionname, "--payload", jsoninput, "_lambada.log"]
		proc = subprocess.Popen(runcode, stdout=subprocess.PIPE)
		stdoutresults = proc.communicate()[0].decode("utf-8")
		jsonoutput = open("_lambada.log").read()
		proc = subprocess.Popen(["rm", "_lambada.log"])
		if "errorMessage" in jsonoutput:
			raise Exception("Lambda Remote Issue: {:s}; runcode: {:s}".format(jsonoutput, " ".join(runcode)))
	output = json.loads(jsonoutput)
	if "log" in output:
		if local:
			if output["log"]:
				print(output["log"])
		else:
			lambada.lambadamonad(output["log"])
	return output["ret"]
"""

proxytemplate = """
def FUNCNAME(PARAMETERSHEAD):
	msg = PACKEDPARAMETERS
	fullresponse = lambda_client.invoke(FunctionName="FUNCNAME_lambda", Payload=json.dumps(msg))
	#response = json.loads(fullresponse["Payload"].read())
	response = json.loads(fullresponse["Payload"].read().decode("utf-8"))
	return response["ret"]
"""

proxytemplate_monadic = """
def FUNCNAME(PARAMETERSHEAD):
	global __lambdalog
	msg = PACKEDPARAMETERS
	fullresponse = lambda_client.invoke(FunctionName="FUNCNAME_lambda", Payload=json.dumps(msg))
	#response = json.loads(fullresponse["Payload"].read())
	response = json.loads(fullresponse["Payload"].read().decode("utf-8"))
	if "log" in response:
		__lambdalog += response["log"]
	return response["ret"]
"""

netproxy_template = """
import json
import importlib
def Netproxy(d, classname, name, args):
	if "." in classname:
		modname, classname = classname.split(".")
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

def netproxy_handler(event, context):
	n = Netproxy(event["d"], event["classname"], event["name"], event["args"])
	return n
"""

def getlambdafunctions(endpoint):
	# historic awscli pre-JSON
	#runcode = "{:s} lambda list-functions | sed 's/.*\(arn:.*:function:.*\)/\\1/' | cut -f 1 | cut -d ':' -f 7".format(awstool(endpoint))
	runcode = "{:s} lambda list-functions | grep FunctionName | cut -d '\"' -f 4".format(awstool(endpoint))
	proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
	stdoutresults = proc.communicate()[0].decode("utf-8")
	lambdafunctions = stdoutresults.strip().split("\n")
	return lambdafunctions

def moveinternal(moveglobals, function, arguments, body, local, lambdafunctions, imports, dependencies, tainted, features, role, debug, endpoint, globalvars, cfc):
	def pack(x):
		return "\"{:s}\": {:s}".format(x, x)
	def unpack(x):
		#return "{:s} = float(event[\"{:s}\"])".format(x, x)
		return "{:s} = event[\"{:s}\"]".format(x, x)

	parameters = arguments.get(function, [])
	unpackparameters = ";".join(map(unpack, parameters))
	packedparameters = "{" + ",".join(map(pack, parameters)) + "}"

	t = template
	t = t.replace("AWSTOOL", ",".join(["\"" + x + "\"" for x in awstool(endpoint).split(" ")]))
	t = t.replace("FUNCNAME", function)
	t = t.replace("PARAMETERSHEAD", ",".join(parameters))
	t = t.replace("PACKEDPARAMETERS", packedparameters)
	t = t.replace("UNPACKPARAMETERS", unpackparameters)
	#print(t)

	#gencode = "\n\t".join(map(lambda node: codegen.to_source(node, indent_with="\t"), body))
	gencode = "\n".join(map(lambda node: "\n".join(["\t" + x for x in codegen.to_source(node, indent_with="\t").split("\n")]), body))
	t = t.replace("FUNCTIONIMPLEMENTATION", gencode[1:])
	#print(t)

	t = t.replace("LOCAL", ("False", "True")[local])

	for module in ("json", "subprocess"):
		if not module in moveglobals:
			exec("import {:s}".format(module), moveglobals)
	if debug and not local:
		print(t)
	exec(t, moveglobals)
	#moveglobals[function] = str

	if local:
		return t
	else:
		lambdafunction = "{:s}_lambda".format(function)
		if lambdafunction in lambdafunctions:
			printlambada("deployer: already deployed {:s}".format(lambdafunction))
		else:
			printlambada("deployer: new deployment of {:s}".format(lambdafunction))

			# FIXME: Lambda is extremely picky about how zip files are constructed... must use tmpdir instead of tmpname
			if True:
				tmpdir = tempfile.TemporaryDirectory()
				filename = "{:s}/{:s}.py".format(tmpdir.name, lambdafunction)
				f = open(filename, "w")
			else:
				f = tempfile.NamedTemporaryFile(suffix=".py", mode="w")
				filename = f.name

			if "print" in features.get(function, []):
				f.write("from __future__ import print_function\n")
				f.write("__lambdalog = ''\n")
				f.write("def print(*args, **kwargs):\n")
				f.write("\tglobal __lambdalog\n")
				f.write("\t__lambdalog += ''.join([str(arg) for arg in args]) + '\\n'\n")
			else:
				# Monadic behaviour: print from dependencies
				monadic = False
				for dep in dependencies.get(function, []):
					if "print" in features.get(dep, []):
						monadic = True
				if monadic:
					f.write("__lambdalog = ''\n")

			# FIXME: workaround, still needed when no print is found anywhere due to template referencing log
			f.write("__lambdalog = ''\n")

			# FIXME: module dependencies are global; missing scanned per-method dependencies
			for importmodule in imports:
				f.write("import {:s}\n".format(importmodule))
			for globalvar in globalvars:
				f.write("{:s} = {:s}\n".format(globalvar[0], globalvar[1]))
			if len(dependencies.get(function, [])) > 0:
				f.write("import json\n")
				f.write("from boto3 import client as boto3_client\n")
				#f.write("lambda_client = boto3_client('lambda')\n")
				if endpoint:
					f.write("lambda_client = boto3_client('lambda', endpoint_url='{:s}')\n".format(endpoint))
				else:
					f.write("lambda_client = boto3_client('lambda')\n")
			f.write("\n")
			for dep in dependencies.get(function, []):
				f.write("# dep {:s}\n".format(dep))
				t = proxytemplate
				if monadic:
					t = proxytemplate_monadic
				depparameters = arguments.get(dep, [])
				packeddepparameters = "{" + ",".join(map(pack, depparameters)) + "}"
				t = t.replace("FUNCNAME", dep)
				t = t.replace("PARAMETERSHEAD", ",".join(depparameters))
				t = t.replace("PACKEDPARAMETERS", packeddepparameters)
				f.write("{:s}\n".format(t))
				f.write("\n")
			f.write("def {:s}(event, context):\n".format(lambdafunction))
			f.write("\t{:s}\n".format(unpackparameters))
			f.write("{:s}\n".format(gencode))
			f.flush()

			zf = tempfile.NamedTemporaryFile(prefix="lambada_", suffix="_{:s}.zip".format(function))
			zipper = zipfile.ZipFile(zf, mode="w")
			zipper.write(f.name, arcname="{:s}.py".format(lambdafunction))
			zipper.close()
			zipname = zf.name

			printlambada("deployer: zip {:s} -> {:s}".format(lambdafunction, zipname))
			runcode = "{:s} lambda create-function --function-name '{:s}' --description 'Lambada remote function' --runtime 'python3.6' --role '{:s}' --handler '{:s}.{:s}' --zip-file 'fileb://{:s}'".format(awstool(endpoint), lambdafunction, role, lambdafunction, lambdafunction, zipname)
			if cfc:
				if cfc.memory:
					runcode += " --memory-size {}".format(cfc.memory)
				if cfc.duration:
					runcode += " --timeout {}".format(cfc.duration)
			proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
			proc.wait()

			reverse = False
			for revdepfunction in dependencies:
				if revdepfunction in tainted:
					continue
				for revdep in dependencies[revdepfunction]:
					if revdep == function:
						reverse = True
			if reverse:
				printlambada("deployer: reverse dependencies require role authorisation")
				runcode = "{:s} lambda add-permission --function-name '{:s}' --statement-id {:s}_reverse --action lambda:InvokeFunction --principal {:s}".format(awstool(endpoint), lambdafunction, lambdafunction, role)
				proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
				proc.wait()

def move(moveglobals, local=False, lambdarolearn=None, module=None, debug=False, endpoint=None, annotations=False):
	if not lambdarolearn and not local:
		printlambada("role not set, trying to read environment variable LAMBDAROLEARN")
		lambdarolearn = os.getenv("LAMBDAROLEARN")
		if not lambdarolearn:
			printlambada("environment variable not set, trying to assemble...")
			runcode = "{} sts get-caller-identity --output text --query 'Account'".format(awstool(endpoint))
			proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
			stdoutresults = proc.communicate()[0].decode("utf-8").strip()
			if len(stdoutresults) == 12:
				lambdarolearn = "arn:aws:iam::{:s}:role/lambda_basic_execution".format(stdoutresults)
				printlambada("... assembled", lambdarolearn)
			if not lambdarolearn:
				raise Exception("Role not set - check lambdarolearn=... or LAMBDAROLEARN=...")
	if not local:
		lambdafunctions = getlambdafunctions(endpoint)
	else:
		lambdafunctions = None
	#print(moveglobals)
	imports = []
	functions = []
	globalvars = []
	classes = []
	for moveglobal in list(moveglobals):
		if type(moveglobals[moveglobal]) == type(ast):
			# = module import
			#print("// import", moveglobal, moveglobals[moveglobal].__name__)
			if moveglobal != moveglobals[moveglobal].__name__:
				moveglobal = "{:s} as {:s}".format(moveglobals[moveglobal].__name__, moveglobal)
			if moveglobal not in ("lambada", "__builtins__"):
				imports.append(moveglobal)
		elif type(moveglobals[moveglobal]) == type(move):
			# = function
			functions.append(moveglobal)
		elif type(moveglobals[moveglobal]) == type(str):
			# = class definition
			#print("// class", moveglobal, "=", moveglobals[moveglobal])
			classes.append(moveglobals[moveglobal])
		elif not moveglobal.startswith("__"):
			# = global variable
			#print("// global variable", moveglobal, "=", moveglobals[moveglobal])
			mgvalue = moveglobals[moveglobal]
			if type(mgvalue) == str:
				mgvalue = "'" + mgvalue + "'"
			else:
				mgvalue = str(mgvalue)
			globalvars.append((moveglobal, mgvalue))
	tainted, args, bodies, dependencies, features, classbodies, cfcs = analyse(None, functions, module, annotations)
	#print("// imports", str(imports))
	tsource = ""
	for classobj in classes:
		functionproxy.scanclass(None, None, classobj.__name__)
	for function in functions:
		#print("**", function, type(moveglobals[function]))
		if function in tainted:
			printlambada("skip tainted", function)
		else:
			printlambada("move", function)
			t = moveinternal(moveglobals, function, args, bodies.get(function, []), local, lambdafunctions, imports, dependencies, tainted, features, lambdarolearn, debug, endpoint, globalvars, cfcs.get(function, None))
			if t:
				tsource += t
		#analyse(function)
	#moveglobals["complextrig"] = complextrigmod

	for classbody in classbodies:
		tsource += codegen.to_source(classbodies[classbody], indent_with="\t")
	if len(classbodies) > 0:
		tsource += netproxy_template

	if tsource:
		for globalvar in globalvars:
			tsource = "{:s} = {:s}\n".format(globalvar[0], globalvar[1]) + tsource
		# FIXME: only needed when monadic...
		tsource = "__lambdalog = ''\n" + tsource
		for importmodule in imports + ["json", "subprocess"]:
			tsource = "import {:s}\n".format(importmodule) + tsource
		if debug:
			print(tsource)
		lambmodule = module.replace(".py", "_lambdafied.py")
		printlambada("store", lambmodule)
		f = open(lambmodule, "w")
		f.write(tsource)
		f.close()
