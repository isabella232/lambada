#!/usr/bin/env python3

import math
import ast
import imp

f1a = ast.arguments([], None, [], [], None, [])

#f1a = ast.arguments()
#f1a.args = []
#f1a.kwonlyargs = []
#f1a.kw_defaults = []
#f1a.defaults = []

#stmt = ast.Assign([ast.Name("x", ast.Store())], "dummyvalue")
p = ast.Pass()

#f1d = ast.FunctionDef("f1n", f1a, [stmt], [], None)
f1d = ast.FunctionDef("f1n", f1a, [p], [], None)

f1d = ast.fix_missing_locations(f1d)
m = ast.Module([f1d])
mc = compile(m, "", "exec")
