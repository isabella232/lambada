import ast

def visitorPrint(s):
	purple = "\033[35m"
	reset = reset = "\033[0m"
	print(purple, s, reset)

class CloudFunctionConfiguration:
	def __init__(self):
		self.enabled = False
		self.memory = None
		self.duration = None
		self.region = None

	def __str__(self):
		return "CloudFunctionConfiguration({}|{}|{})".format(self.memory, self.duration, self.region)

	def __format__(self, s):
		return self.__str__()

class FuncListener(ast.NodeVisitor):
	def __init__(self, functions, annotations, functionname=None):
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
		self.cloudfunctionconfigs = {}

	def checkdep(self, dep):
		if dep in self.functions and not dep in self.deps.get(self.currentfunction, []):
			visitorPrint("AST: dependency {:s} -> {:s}".format(self.currentfunction, dep))
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
		d = ast.Dict([ast.Str("ret"), ast.Str("log")], [node.value, ast.Name("__lambadalog", ast.Load())])

		node.value = d

	def visit_FunctionDef(self, node):
		self.currentfunction = node.name

		if self.annotations:
			if node.name == "cloudfunction":
				self.generic_visit(node)
			
			cloudfunctionconfig = CloudFunctionConfiguration()

			for name in node.decorator_list:
				if "id" in dir(name):
					if name.id == "cloudfunction":
						cloudfunctionconfig.enabled = True
				else:
					if name.func.id == "cloudfunction":
						cloudfunctionconfig.enabled = True

						for keyword in name.keywords:
							if keyword.arg == "memory":
								cloudfunctionconfig.memory = keyword.value.n
							elif keyword.arg == "region":
								cloudfunctionconfig.region = keyword.value.s
							elif keyword.arg == "duration":
								cloudfunctionconfig.duration = keyword.value.n

			if cloudfunctionconfig.enabled:
				visitorPrint(("AST: annotation {:s} @ {:s}".format(cloudfunctionconfig, node.name)))
				self.cloudfunctionconfigs[node.name] = cloudfunctionconfig
			else:
				visitorPrint(("AST: no annotation @ {:s}".format(node.name)))
				self.generic_visit(node)
				self.filtered.append(node.name)

		if self.functionname == None or node.name == self.functionname:
			for arg in node.args.args:
				pass
			for linekind in node.body:
				if isinstance(linekind, ast.Expr):
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
			
			newbody = []

			for linekind in node.body:
				if isinstance(linekind, ast.Return):
					assignret = ast.Assign([ast.Name("ret", ast.Store())], linekind.value)
					dictreturn = ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambadalog", ast.Load())])
					changeret = ast.Assign([ast.Name("ret", ast.Store())], dictreturn)
					returnstatement = ast.Return(ast.Name("ret", ast.Load()))
					globalstatement = ast.Global(["__lambadalog"])
					resetlog = ast.Assign([ast.Name("__lambadalog", ast.Store())], ast.Str(""))

					# FIXME: always assume log because here the monadic situation through dependencies is not yet clear
					newbody = [globalstatement] + newbody + [assignret, changeret, resetlog, returnstatement]
				else:
					newbody.append(linekind)
		
			self.bodies[node.name] = newbody
		
		self.generic_visit(node)

class FuncListenerGCloud(FuncListener):
	def visit_FunctionDef(self, node):
		self.currentfunction = node.name

		if self.annotations:
			if node.name == "cloudfunction":
				self.generic_visit(node)
			
			cloudfunctionconfig = CloudFunctionConfiguration()
			
			for name in node.decorator_list:
				if "id" in dir(name):
					if name.id == "cloudfunction":
						cloudfunctionconfig.enabled = True
				else:
					if name.func.id == "cloudfunction":
						cloudfunctionconfig.enabled = True

						for keyword in name.keywords:
							if keyword.arg == "memory":
								cloudfunctionconfig.memory = keyword.value.n
							elif keyword.arg == "region":
								cloudfunctionconfig.region = keyword.value.s
							elif keyword.arg == "duration":
								cloudfunctionconfig.duration = keyword.value.n

			if cloudfunctionconfig.enabled:
				visitorPrint(("AST: annotation {:s} @ {:s}".format(cloudfunctionconfig, node.name)))
				self.cloudfunctionconfigs[node.name] = cloudfunctionconfig
			else:
				visitorPrint(("AST: no annotation @ {:s}".format(node.name)))
				self.generic_visit(node)
				self.filtered.append(node.name)

		if self.functionname == None or node.name == self.functionname:
			for arg in node.args.args:
				pass
			
			for linekind in node.body:
				if isinstance(linekind, ast.Expr):
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
			
			newbody = []

			for linekind in node.body:
				if isinstance(linekind, ast.Return):
					assignret = ast.Assign([ast.Name("ret", ast.Store())], linekind.value)
					dictreturn = ast.Dict([ast.Str("ret"), ast.Str("log")], [ast.Name("ret", ast.Load()), ast.Name("__lambadalog", ast.Load())])
					calljsonify = ast.Call(func=ast.Name("jsonify", ast.Load()), args=[dictreturn], keywords=[])
					changeret = ast.Assign([ast.Name("ret", ast.Store())], calljsonify)
					returnstatement = ast.Return(ast.Name("ret", ast.Load()))
					globalstatement = ast.Global(["__lambadalog"])
					resetlog = ast.Assign([ast.Name("__lambadalog", ast.Store())], ast.Str(""))
					importflask = ast.ImportFrom("flask", [ast.alias(name='jsonify', asname=None)], 0)
			
					# FIXME: always assume log because here the monadic situation through dependencies is not yet clear
					newbody = [importflask, globalstatement] + newbody + [assignret, changeret, resetlog, returnstatement]
				else:
					newbody.append(linekind)
			
			self.bodies[node.name] = newbody

		self.generic_visit(node)
	
	
	def visit_Return(self, node):
		t = ast.Tuple(node.value, ast.Name("__lambadalog", ast.Load()))
		
		node.value = t
        