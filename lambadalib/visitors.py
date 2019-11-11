import ast

def color(s):
    return "\033[70m" + s + "\033[0m"

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
			print(color("AST: dependency {:s} -> {:s}".format(self.currentfunction, dep)))
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
		d = ast.Dict([ast.Str("ret"), ast.Str("log")], [node.value, ast.Name("__lambadalog", ast.Load())])
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
				print(color(("AST: annotation {:s} @ {:s}".format(cfc, node.name))))
				self.cfcs[node.name] = cfc
			else:
				print(color(("AST: no annotation @ {:s}".format(node.name))))
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
					d = ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambadalog", ast.Load())])
					b = ast.Assign([ast.Name("ret", ast.Store())], d)
					r = ast.Return(ast.Name("ret", ast.Load()))
					g = ast.Global(["__lambadalog"])
					z = ast.Assign([ast.Name("__lambadalog", ast.Store())], ast.Str(""))

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

class FuncListenerRequest(FuncListener):
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
				print(color(("AST: annotation {:s} @ {:s}".format(cfc, node.name))))
				self.cfcs[node.name] = cfc
			else:
				print(color(("AST: no annotation @ {:s}".format(node.name))))
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
					d = ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambadalog", ast.Load())])
					c = ast.Call(func=ast.Name("jsonify", ast.Load()), args=[d], keywords=[])
					b = ast.Assign([ast.Name("ret", ast.Store())], c)
					r = ast.Return(ast.Name("ret", ast.Load()))
					g = ast.Global(["__lambadalog"])
					z = ast.Assign([ast.Name("__lambadalog", ast.Store())], ast.Str(""))
					i = ast.ImportFrom("flask", [ast.alias(name='jsonify', asname=None)], 0)
			
					# FIXME: always assume log because here the monadic situation through dependencies is not yet clear
					#if "print" in self.features.get(node.name, []):
					#	r = ast.Return(ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambdalog", ast.Load())]))
					#else:
					#	r = ast.Return(ast.Dict([ast.Str("ret")], [ast.Name("ret", ast.Load())]))
					#print("//return", linekind.value)
					#print(ast.dump(a, annotate_fields=False))
					#print(ast.dump(r, annotate_fields=False))
					newbody = [i, g] + newbody + [a, b, z, r]
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
	
	
	def visit_Return(self, node):
		t = ast.Tuple(node.value, ast.Name("__lambadalog", ast.Load()))
		
		node.value = t
        