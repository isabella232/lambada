# Lambada - Main module

import inspect
import ast
#import astor.codegen as codegen
import tempfile
import zipfile
import subprocess
import time
import os

from lambadalib.codegen import code_gen as codegen
from lambadalib import functionproxy
from lambadalib import providers

def printlambada(*s):
	red = "\033[1;31m"
	reset = "\033[0;0m"
	s += (reset,)
	print(red, "»» Lambada:", *s)

def lambadamonad(s):
	green = "\033[1;32m"
	reset = "\033[0;0m"
	print(green, "»» Lambada Monad:", s, reset)

def analyse(functionname, functions, module, annotations, provider):
	if not module:
		modulename = inspect.stack()[-1][1]
		printlambada("targeting", modulename, "...")
	else:
		modulename = module

	modulestring = open(modulename).read()
	tree = ast.parse(modulestring, modulename)
	fl = provider.getNodeVisitor(functionname, functions, annotations)
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

def moveinternal(moveglobals, function, arguments, body, local, imports, dependencies, tainted, features, debug, globalvars, cfc, provider = providers.AWSLambda()):

	if not local:
		cloudfunctions = provider.getCloudFunctions()
	else:
		cloudfunctions = None

	def pack(x):
		return "\"{:s}\": {:s}".format(x, x)
	def unpack(x):
		#return "{:s} = float(event[\"{:s}\"])".format(x, x)
		return "{:s} = {:s}[\"{:s}\"]".format(provider.getArgsVariable, x, x)

	parameters = arguments.get(function, [])
	unpackparameters = ";".join(map(unpack, parameters))
	packedparameters = "{" + ",".join(map(pack, parameters)) + "}"

	t = provider.getTemplate()
	t = t.replace("FUNCNAME", function)
	t = t.replace("PROVNAME", provider.getName())
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
		cloudfunction = "{:s}_{:s}".format(function, provider.getName())

		if cloudfunction in cloudfunctions:
			printlambada("deployer: already deployed {:s}".format(cloudfunction))
		else:
			printlambada("deployer: new deployment of {:s}".format(cloudfunction))

			#TODO check?
			# FIXME: Lambda is extremely picky about how zip files are constructed... must use tmpdir instead of tmpname
			if True:
				tmpdir = tempfile.TemporaryDirectory()
				filename = "{:s}/{:s}.py".format(tmpdir.name, cloudfunction)
				f = open(filename, "w")
			else:
				f = tempfile.NamedTemporaryFile(suffix=".py", mode="w")
				filename = f.name

			if "print" in features.get(function, []):
				f.write("from __future__ import print_function\n")
				f.write("__lambadalog = ''\n")
				f.write("def print(*args, **kwargs):\n")
				f.write("\tglobal __lambadalog\n")
				f.write("\t__lambadalog += ''.join([str(arg) for arg in args]) + '\\n'\n")
			else:
				# Monadic behaviour: print from dependencies
				monadic = False
				for dep in dependencies.get(function, []):
					if "print" in features.get(dep, []):
							monadic = True
					if monadic:
						f.write("__lambadalog = ''\n")

			# FIXME: workaround, still needed when no print is found anywhere due to template referencing log
			f.write("__lambadalog = ''\n")

			# FIXME: module dependencies are global; missing scanned per-method dependencies
			for importmodule in imports:
				f.write("import {:s}\n".format(importmodule))

			for globalvar in globalvars:
				f.write("{:s} = {:s}\n".format(globalvar[0], globalvar[1]))

			if len(dependencies.get(function, [])) > 0:
				f.write(provider.getHttpClientTemplate())

			f.write("\n")
				
			for dep in dependencies.get(function, []):
				f.write("# dep {:s}\n".format(dep))
				t = provider.getProxyTemplate()

				if monadic:
					t = provider.getProxyMonadicTemplate()

				depparameters = arguments.get(dep, [])
				packeddepparameters = "{" + ",".join(map(pack, depparameters)) + "}"
				t = t.replace("FUNCNAME", dep)
				t = t.replace("PROVNAME", provider.getName())
				t = t.replace("PARAMETERSHEAD", ",".join(depparameters))
				t = t.replace("PACKEDPARAMETERS", packeddepparameters)
				f.write("{:s}\n".format(t))
				f.write("\n")

			f.write(provider.getFunctionSignature(cloudfunction))

			f.write("\t{:s}\n".format(unpackparameters))
			f.write("{:s}\n".format(gencode))
			f.flush()

			zf = tempfile.NamedTemporaryFile(prefix="lambada_", suffix="_{:s}.zip".format(function))
			zipper = zipfile.ZipFile(zf, mode="w")
			zipper.write(f.name, arcname=provider.getMainFilename(cloudfunction))
			zipper.close()
			zipname = zf.name

			printlambada("deployer: zip {:s} -> {:s}".format(cloudfunction, zipname))

			runcode = provider.getCreationString(cloudfunction, zf, cfc)

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
				runcode = provider.getAddPermissionString(cloudfunction)
				if runcode:
					printlambada("deployer: reverse dependencies require role authorisation")
					proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
					proc.wait()	


def move(moveglobals, local=False, lambdarolearn=None, module=None, debug=False, endpoint=None, annotations=False, cloudprovider=None):

	#Set provider
	provider = providers.getProvider(cloudprovider, endpoint, lambdarolearn)

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
	
	tainted, args, bodies, dependencies, features, classbodies, cfcs = analyse(None, functions, module, annotations, provider)

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
			t = moveinternal(moveglobals, function, args, bodies.get(function, []), local, imports, dependencies, tainted, features, debug, globalvars, cfcs.get(function, None), provider)
			if t:
				tsource += t
		#analyse(function)
	
	#moveglobals["complextrig"] = complextrigmod

	for classbody in classbodies:
		tsource += codegen.to_source(classbodies[classbody], indent_with="\t")
	
	#TODO check netproxy_template for both	
	if len(classbodies) > 0:
		tsource += provider.getNetproxyTemplate()

	#TODO check
	if tsource:
		for globalvar in globalvars:
			tsource = "{:s} = {:s}\n".format(globalvar[0], globalvar[1]) + tsource
		# FIXME: only needed when monadic...
		tsource = "__lambadalog = ''\n" + tsource
		for importmodule in imports + ["json", "subprocess"]:
			tsource = "import {:s}\n".format(importmodule) + tsource
		if debug:
			print(tsource)
		lambmodule = module.replace(".py", "_lambadafied.py")
		printlambada("store", lambmodule)
		f = open(lambmodule, "w")
		f.write(tsource)
		f.close()