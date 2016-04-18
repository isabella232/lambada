#!/usr/bin/env python3
#
# Partially (complextrig only) JSON-ified variant of ../myapp.py
# Switch: local=False/True in complextrig(v)

import math
import csv

import json
import subprocess

# This would be the remote function (renamed to complextrig_lambda.py)
def complextrig_remote(event, context):
	v = float(event["v"])
	ret = math.sin(v) + math.cos(v)
	return {"ret": ret}

def complextrig_stub(jsoninput):
	event = json.loads(jsoninput)
	ret = complextrig_remote(event, None)
	return json.dumps(ret)

def complextrig(v):
	local = False
	jsoninput = json.dumps({"v": v})
	if local:
		jsonoutput = complextrig_stub(jsoninput)
	else:
		functionname = "complextrig_lambda"
		logfile = "_myapp.log"
		proc = subprocess.Popen(["aws", "lambda", "invoke", "--function-name", functionname, "--payload", jsoninput, logfile], stdout=subprocess.PIPE)
		stdoutresults = proc.communicate()[0].decode("utf-8")
		jsonoutput = open(logfile).read()
		#print("ANSWER #{:s}#".format(jsonoutput))
		proc = subprocess.Popen(["rm", logfile])
		if "errorMessage" in jsonoutput:
			raise Exception("Lambda Remote Issue!")
	return json.loads(jsonoutput)["ret"]

def calculate(values):
	return sum(map(complextrig, values))

def calculatecsv():
	values = []
	with open("../values.csv") as f:
		reader = csv.reader(f)
		for row in reader:
			values.append(int(row[1]))
	return calculate(values)

if __name__ == "__main__":
	print(calculate([98, 99, 100]))
	print(calculatecsv())
