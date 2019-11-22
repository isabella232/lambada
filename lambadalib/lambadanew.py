# Lambada - Main module

import inspect
import ast
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

def analyse(functions, module, annotations, provider):
	if not module:
		modulename = inspect.stack()[-1][1]
		printlambada("targeting", modulename, "...")
	else:
		modulename = module

	modulestring = open(modulename).read()
	tree = ast.parse(modulestring, modulename)
	nodevisitor = provider.getNodeVisitor(functions=functions, annotations=annotations)
	nodevisitor.visit(tree)
	
	for function in functions:
		for dep in nodevisitor.deps.get(function, []):
			if dep in nodevisitor.tainted:
				printlambada("AST: dependency {:s} -> {:s} leads to tainting".format(function, dep))
				nodevisitor.tainted.append(function)
	
	for function in functions:
		for dep in nodevisitor.deps.get(function, []):
			if dep in nodevisitor.filtered:
				taint = True

				if taint:
					nodevisitor.tainted.append(dep)
	
	return nodevisitor.tainted, nodevisitor.args, nodevisitor.bodies, nodevisitor.deps, nodevisitor.features, nodevisitor.classes, nodevisitor.cloudfunctionconfigs

def moveinternal(moveglobals, function, arguments, body, local, imports, dependencies, tainted, features, debug, globalvars, cloudfunctionconfig, provider = providers.AWSLambda()):

	if not local:
		cloudfunctions = provider.getCloudFunctions()
	else:
		cloudfunctions = None

	def pack(x):
		return "\"{:s}\": {:s}".format(x, x)
	
	def unpack(x):
		return "{:s} = {:s}[\"{:s}\"]".format(x, provider.getArgsVariable(), x)

	parameters = arguments.get(function, [])
	unpackparameters = ";".join(map(unpack, parameters))
	packedparameters = "{" + ",".join(map(pack, parameters)) + "}"

	template = provider.getTemplate()
	template = template.replace("FUNCNAME", function)
	template = template.replace("PROVNAME", provider.getName())
	template = template.replace("PARAMETERSHEAD", ",".join(parameters))
	template = template.replace("PACKEDPARAMETERS", packedparameters)
	template = template.replace("UNPACKPARAMETERS", unpackparameters)

	gencode = "\n".join(map(lambda node: "\n".join(["\t" + x for x in codegen.to_source(node, indent_with="\t").split("\n")]), body))
	template = template.replace("FUNCTIONIMPLEMENTATION", gencode[1:])

	template = template.replace("LOCAL", ("False", "True")[local])

	for module in ("json", "subprocess"):
		if not module in moveglobals:
			exec("import {:s}".format(module), moveglobals)
	
	if debug and not local:
		print(template)
	
	exec(template, moveglobals)
	#moveglobals[function] = str

	if local:
		return template
	else:
		cloudfunction = "{:s}-{:s}".format(function, provider.getName())

		if cloudfunction in cloudfunctions:
			printlambada("deployer: already deployed {:s}".format(cloudfunction))
		else:
			printlambada("deployer: new deployment of {:s}".format(cloudfunction))

			#TODO check?
			# FIXME: Lambda is extremely picky about how zip files are constructed... must use tmpdir instead of tmpname
			if True:
				tmpdir = tempfile.TemporaryDirectory()
				filename = "{:s}/{:s}.py".format(tmpdir.name, cloudfunction)
				pyfile = open(filename, "w")
			else:
				pyfile = tempfile.NamedTemporaryFile(suffix=".py", mode="w")
				filename = pyfile.name

			if "print" in features.get(function, []):
				pyfile.write("from __future__ import print_function\n")
				pyfile.write("__lambadalog = ''\n")
				pyfile.write("def print(*args, **kwargs):\n")
				pyfile.write("\tglobal __lambadalog\n")
				pyfile.write("\t__lambadalog += ''.join([str(arg) for arg in args]) + '\\n'\n")
			else:
				# Monadic behaviour: print from dependencies
				monadic = False
				for dep in dependencies.get(function, []):
					if "print" in features.get(dep, []):
							monadic = True
					if monadic:
						pyfile.write("__lambadalog = ''\n")

			# FIXME: workaround, still needed when no print is found anywhere due to template referencing log
			pyfile.write("__lambadalog = ''\n")

			# FIXME: module dependencies are global; missing scanned per-method dependencies
			for importmodule in imports:
				pyfile.write("import {:s}\n".format(importmodule))

			for globalvar in globalvars:
				pyfile.write("{:s} = {:s}\n".format(globalvar[0], globalvar[1]))

			if len(dependencies.get(function, [])) > 0:
				pyfile.write(provider.getHttpClientTemplate())

			pyfile.write("\n")
				
			for dep in dependencies.get(function, []):
				pyfile.write("# dep {:s}\n".format(dep))
				template = provider.getProxyTemplate()

				if monadic:
					template = provider.getProxyMonadicTemplate()

				depparameters = arguments.get(dep, [])
				packeddepparameters = "{" + ",".join(map(pack, depparameters)) + "}"
				template = template.replace("FUNCNAME", dep)
				template = template.replace("PROVNAME", provider.getName())
				template = template.replace("PARAMETERSHEAD", ",".join(depparameters))
				template = template.replace("PACKEDPARAMETERS", packeddepparameters)
				pyfile.write("{:s}\n".format(template))
				pyfile.write("\n")

			pyfile.write(provider.getFunctionSignature(cloudfunction))

			pyfile.write("\t{:s}\n".format(unpackparameters))
			pyfile.write("{:s}\n".format(gencode))
			pyfile.flush()

			tempzip = tempfile.NamedTemporaryFile(prefix="lambada_", suffix="_{:s}.zip".format(function))
			zipper = zipfile.ZipFile(tempzip, mode="w")
			zipper.write(pyfile.name, arcname=provider.getMainFilename(cloudfunction))
			zipper.close()
			zipname = tempzip.name

			printlambada("deployer: zip {:s} -> {:s}".format(cloudfunction, zipname))

			runcode = provider.getCreationString(cloudfunction, tempzip, cloudfunctionconfig)

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


def move(moveglobals, local=False, module=None, debug=False, annotations=False, cloudprovider=None, cloudproviderargs=None):

	#Set provider
	provider = providers.getProvider(cloudprovider, cloudproviderargs)

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
	
	tainted, args, bodies, dependencies, features, classbodies, cloudfunctionconfigs = analyse(functions, module, annotations, provider)

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
			filledtemplate = moveinternal(moveglobals, function, args, bodies.get(function, []), local, imports, dependencies, tainted, features, debug, globalvars, cloudfunctionconfigs.get(function, None), provider)
			if filledtemplate:
				tsource += filledtemplate
	
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