#!/usr/bin/env python3
#
# Function splitter as separate tool useful for Lambada

import ast
import imp
import sys
import argparse
import copy
import os
import time

class FuncSplitter:
	def __init__(self):
		self.debug = False
		self.splitloops = False
		self.splitsleep = False

	def printdebug(self, *s):
		if self.debug:
			red = ""
			if os.isatty(sys.stdout.fileno()):
				red = "\033[1;35m"
				reset = "\033[0;0m"
				s += (reset,)
			print(red, "»» fs:", *s)

	def funcsplitter(self, modulename, functionname, arguments, splitrange=None):
		try:
			fileobj = open(modulename)
		except:
			try:
				fileobj, path, description = imp.find_module(modulename)
			except:
				fileobj = None
			if not fileobj or description[2] != imp.PY_SOURCE:
				raise Exception("Module or script {} not found.".format(modulename))
			exec("from {} import *".format(modulename))
			for entry in dir():
				globals()[entry] = eval(entry)
		modcode = fileobj.read()

		fname = None
		tree = ast.parse(modcode)
		for item in tree.body:
			if isinstance(item, ast.Import):
				for name in item.names:
					self.printdebug("Import", name.name)
					exec("import {}".format(name.name))
					globals()[name.name] = eval(name.name)
			if isinstance(item, ast.FunctionDef):
				if item.name == functionname:
					if len(item.args.args) > 0:
						self.printdebug("Args", dir(item.args.args[0]), item.args.args[0].arg)
					fname = item.name

					self.splitcombinatorial(item, arguments, globals(), splitrange)

		if not fname:
			raise Exception("Function {} not found in module or script.".format(functionname))

	def formatargs(self, args, quoting=True):
		if not quoting:
			return args
		self.printdebug("args >>", args, quoting)
		if type(args) == list:
			for i, arg in enumerate(args):
				if type(arg) != str:
					evarg = "'{}'".format(arg)
				else:
					evarg = arg
				try:
					eval(evarg)
				except:
					args[i] = "\"{}\"".format(arg)
			if quoting:
				args = ",".join([str(arg) for arg in args])
		self.printdebug("args <<", args)
		return args

	def splitcombinatorial(self, item, arguments, ctx, splitrange):
		functionname = item.name
		for k in ctx:
			globals()[k] = ctx[k]

		if not splitrange:
			splitrange = range(1, len(item.body))
		for i in splitrange:
			handover = []
			resolved = []
			for j in range(0, i):
				if isinstance(item.body[j], ast.Assign):
					if "id" in dir(item.body[j].targets[0]):
						# Name
						target = item.body[j].targets[0].id
						if not target in handover:
							handover.append(target)
					elif "elts" in dir(item.body[j].targets[0]):
						# Tuple
						for name in item.body[j].targets[0].elts:
							if "id" in dir(name):
								target = name.id
								if not target in handover:
									handover.append(target)
				if isinstance(item.body[j], ast.Import):
					for name in item.body[j].names:
						exec("import {}".format(name.name))
						handover.append(name.name)
						resolved.append(name.name)
			self.printdebug(i, item.body[:i], item.body[i:], handover)
			f1a = item.args
			f2a = ast.arguments([], None, [], [], None, [])
			for arg in handover:
				f2a.args.append(ast.arg(arg, None))
			for arg in item.args.args:
				if not arg.arg in handover:
					handover.append(arg.arg)
					f2a.args.append(arg)
			f1n = "{}_1_{}".format(functionname, i)
			f2n = "{}_2_{}".format(functionname, i)
			returnlist = []
			self.printdebug("split {}/{}: » {}".format(i, len(item.body) - i, handover))
			for arg in handover:
				if arg in resolved:
					returnlist.append(ast.Name(arg, ast.Load()))
				else:
					returnlist.append(ast.Name(arg, ast.Load()))
			ireturn = ast.Return(ast.List(returnlist, ast.Load()))
			looppart = []
			if self.splitloops:
				if isinstance(item.body[i], ast.For):
					loop = item.body[i]
					self.printdebug("Loop!", dir(loop), loop.iter.args[0].n, loop.target.id, loop.iter.func.id)
					iterpart = copy.deepcopy(loop.iter)
					loop.iter.args[0].n //= 2
					iterpart.args[0].n //= 2
					looppart.append(ast.For(loop.target, iterpart, loop.body, loop.orelse))
			if self.splitsleep:
				if isinstance(item.body[i], ast.Expr):
					call = item.body[i].value
					if "value" in dir(call.func) and call.func.value.id == "time" and call.func.attr == "sleep":
						self.printdebug("Sleep!", call.args[0].n)
						sleeppart = copy.deepcopy(call)
						call.args[0].n /= 2
						sleeppart.args[0].n /= 2
						looppart.append(ast.Expr(call))
			f1d = ast.FunctionDef(f1n, f1a, item.body[:i] + looppart + [ireturn], [], None)
			f2d = ast.FunctionDef(f2n, f2a, item.body[i:], [], None)
			m = ast.Module(body=[f1d, f2d])
			m = ast.fix_missing_locations(m)
			mc = compile(m, "", "exec")
			me = exec(mc)
			e_f1 = "{}({})".format(f1n, self.formatargs(arguments))
			t_f1 = -0.0
			t_f2 = -0.0
			try:
				s_time = time.time()
				ret_f1 = eval(e_f1)
				t_f1 = time.time() - s_time
			except Exception as e:
				result = "faulty F1: {} {}".format(e, e_f1)
				self.printdebug(result)
				self.printdebug(sys.exc_info()[1])
			else:
				self.printdebug("F1 result", ret_f1)
				args = ret_f1

				self.printdebug("F2 params: {}".format(len(args)))
				for arg in args:
					newname = "arg[...]"
					self.printdebug("-> F2 param: {} = {}".format(newname, type(arg)))
				args = self.formatargs(args, quoting=False)

				e_f2 = "{}(*args)".format(f2n)
				try:
					s_time = time.time()
					ret_f2 = eval(e_f2)
					t_f2 = time.time() - s_time
				except Exception as e:
					result = "faulty F2: {} {}".format(e, e_f2)
					self.printdebug(result)
					self.printdebug(sys.exc_info()[1])
				else:
					result = ret_f2
					self.printdebug("F2 result", result)
			timing = "{:4.2f} {:4.2f}".format(t_f1, t_f2)
			print("split {}/{}: result={} times={}".format(i, len(item.body) - i, result, timing))

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='FuncSplitter - Divides functions into smaller ones')
	parser.add_argument('modulename', metavar='modulename', type=str, help='module file containing the function')
	parser.add_argument('functionname', metavar='functionname', type=str, help='name of the function')
	parser.add_argument('arguments', metavar='arguments', nargs='*', type=str, help='arguments to the function')

	parser.add_argument('--debug', dest='debug', action='store_const', const=True, default=False, help='debugging mode (default: false)')
	parser.add_argument('--split-loops', dest='splitloops', action='store_const', const=True, default=False, help='split loops (default: false)')
	parser.add_argument('--split-sleeps', dest='splitsleeps', action='store_const', const=True, default=False, help='split sleep calls (default: false)')

	args = parser.parse_args()

	fs = FuncSplitter()
	fs.debug = args.debug
	fs.splitloops = args.splitloops
	fs.splitsleeps = args.splitsleeps

	try:
		fs.funcsplitter(args.modulename, args.functionname, args.arguments)
	except Exception as e:
		print("Function splitting failed: {}".format(e), file=sys.stderr)
		sys.exit(1)
