import csv
import math
import json
from boto3 import client as boto3_client
lambda_client = boto3_client('lambda')

# dep complextrig

def complextrig(v):
	msg = {"v": v}
	fullresponse = lambda_client.invoke(FunctionName="complextrig_lambda", Payload=json.dumps(msg))
	response = json.loads(fullresponse["Payload"].read())
	return response["ret"]


def calculate_lambda(event, context):
	values = event["values"]
	ret = sum(map(complextrig, values))
	return {'ret': ret}
