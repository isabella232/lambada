import math
import csv

def complextrig_lambda(event, context):
	v = event["v"]
	ret = math.sin(v) + math.cos(v)
	return {'ret': ret}
