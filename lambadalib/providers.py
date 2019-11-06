import subprocess
import os
import zipfile as Zipfile

from abc import ABC, abstractmethod

def color(s):
    return "\033[39m" + s + "\033[0m"

# Accepted arguments as providers. The first value will be default
PROVIDERS = ['lambda', 'whisk', 'ibm', 'google']

def getProvider(provider, endpoint, role):
    if not provider or provider == PROVIDERS[0]:
        return AWSLambda(endpoint, role)
    elif provider == PROVIDERS[1]:
        return OpenWhisk(endpoint, role)
    elif provider == PROVIDERS[2]:
        return IBMCloud(endpoint, role)
    elif provider == PROVIDERS[3]:
        return GoogleCloud(endpoint, role)
    
class Provider(ABC):

    @abstractmethod
    def __init__(self, endpoint=None, role=None):
        self.endpoint = endpoint

    @abstractmethod
    def getTool(self, endpoint):
        pass

    @abstractmethod
    def getCloudFunctions(self, endpoint):
        pass

    @abstractmethod
    def getTemplate(self):
        pass

    @abstractmethod
    def getName(self):
        pass

    @abstractmethod
    def getFunctionSignature(self, name):
        pass

    @abstractmethod
    def getMainFilename(self, name):
        pass

    @abstractmethod
    def getCreationString(self, functionname, zipfile, cfc=None):
        pass
    
    @abstractmethod
    def getAddPermissionString(self, name):
        pass

    @abstractmethod
    def getHttpClientTemplate(self):
        pass

    @abstractmethod
    def getArgsVariable(self):
        pass

    @abstractmethod
    def getProxyTemplate(self):
        pass

    @abstractmethod
    def getProxyMonadicTemplate(self):
        pass

    @abstractmethod
    def getNetproxyTemplate(self):
        pass

awstemplate = """
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
		functionname = "FUNCNAME_PROVNAME"
		runcode = [CLOUDTOOL, "lambda", "invoke", "--function-name", functionname, "--payload", jsoninput, "_lambada.log"]
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

awshttpclienttemplate = """
import json

from boto3 import client as boto3_client

hasendpoint = HASENDPOINT

if hasendpoint:
	lambda_client = boto3_client('lambda', endpoint_url='ENDPOINT')
else:
	lambda_client = boto3_client('lambda')
"""

awsproxytemplate = """
def FUNCNAME(PARAMETERSHEAD):
	msg = PACKEDPARAMETERS
	fullresponse = lambda_client.invoke(FunctionName="FUNCNAME_PROVNAME", Payload=json.dumps(msg))
	#response = json.loads(fullresponse["Payload"].read())
	response = json.loads(fullresponse["Payload"].read().decode("utf-8"))

	return response["ret"]
"""

awsproxymonadictemplate = """
def FUNCNAME(PARAMETERSHEAD):
	global __lambadalog
	
	msg = PACKEDPARAMETERS
	fullresponse = lambda_client.invoke(FunctionName="FUNCNAME_PROVNAME", Payload=json.dumps(msg))
	#response = json.loads(fullresponse["Payload"].read())
	response = json.loads(fullresponse["Payload"].read().decode("utf-8"))
	
	if "log" in response:
		__lambadalog += response["log"]

	return response["ret"]
"""

awsnetproxytemplate = """
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

class AWSLambda(Provider):

    def __init__(self, endpoint=None, role=None):
        super(AWSLambda, self).__init__(endpoint)
        self.lambdarolearn = role

    def getTool(self):
        if self.endpoint:
            return "aws --endpoint-url {:s}".format(self.endpoint)
        else:
            return "aws"

    def getCloudFunctions(self):
        # historic awscli pre-JSON
		#runcode = "{:s} lambda list-functions | sed 's/.*\(arn:.*:function:.*\)/\\1/' | cut -f 1 | cut -d ':' -f 7".format(awstool(endpoint))
        runcode = "{:s} lambda list-functions | grep FunctionName | cut -d '\"' -f 4".format(self.getTool())
        proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
        stdoutresults = proc.communicate()[0].decode("utf-8")
        cloudfunctions = stdoutresults.strip().split("\n")
        
        return cloudfunctions

    def getTemplate(self):
        return awstemplate.replace("CLOUDTOOL", ",".join(["\"" + x + "\"" for x in self.getTool().split(" ")]))

    def getName(self):
        return "lambda"

    def getFunctionSignature(self, name):
        return "def {:s}(event, context):\n".format(name)

    def getMainFilename(self, name):
        return "{:s}.py".format(name)

    def setRole(self):
        if not self.lambdarolearn:
            print(color("Role not set, trying to read environment variable LAMBDAROLEARN"))
            self.lambdarolearn = os.getenv("LAMBDAROLEARN")
		    
            if not self.lambdarolearn:
                print(color("Environment variable not set, trying to assemble..."))
                runcode = "{} sts get-caller-identity --output text --query 'Account'".format(self.getTool())
                proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
                stdoutresults = proc.communicate()[0].decode("utf-8").strip()
			    
                if len(stdoutresults) == 12:
                    self.lambdarolearn = "arn:aws:iam::{:s}:role/lambda_basic_execution".format(stdoutresults)
                    print(color(("... assembled", self.lambdarolearn)))
                    
                if not self.lambdarolearn:
                    raise Exception("Role not set - check lambdarolearn=... or LAMBDAROLEARN=...")

    def getCreationString(self, functionname, zipfile, cfc=None):
        self.setRole()

        runcode = "{:s} lambda create-function --function-name '{:s}' --description 'Lambada remote function' --runtime 'python3.6' --role '{:s}' --handler '{:s}.{:s}' --zip-file 'fileb://{:s}'".format(self.getTool(), functionname, self.lambdarolearn, functionname, functionname, zipfile.name)
		
        if cfc:
            if cfc.memory:
                runcode += " --memory-size {}".format(cfc.memory)
            if cfc.duration:
                runcode += " --timeout {}".format(cfc.duration)
        
        return runcode

    def getAddPermissionString(self, name):
        self.setRole()

        runcode = "{:s} lambda add-permission --function-name '{:s}' --statement-id {:s}_reverse --action lambda:InvokeFunction --principal {:s}".format(self.getTool(), name, name, self.lambdarolearn)

        return runcode

    def getHttpClientTemplate(self):
        template = awshttpclienttemplate
        template = template.replace("HASENDPOINT", "{:s}".format(bool(self.endpoint)))
        
        if(self.endpoint):
            template = template.replace("ENDPOINT", self.endpoint)

        return template

    def getArgsVariable(self):
        return "event"

    def getProxyTemplate(self):
        return awsproxytemplate

    def getProxyMonadicTemplate(self):
        return awsproxymonadictemplate

    def getNetproxyTemplate(self):
        return awsnetproxytemplate

whisktemplate = """
def FUNCNAME_remote(args):
	UNPACKPARAMETERS
	FUNCTIONIMPLEMENTATION

def FUNCNAME_stub(jsoninput):
	args = json.loads(jsoninput)
	ret = FUNCNAME_remote(args)
	return json.dumps(ret)

def FUNCNAME(PARAMETERSHEAD):
	local = LOCAL
	jsoninput = json.dumps(PACKEDPARAMETERS)

	if local:
		jsonoutput = FUNCNAME_stub(jsoninput)
	else:
		functionname = "FUNCNAME_PROVNAME"
		runcode = [CLOUDTOOL, "action", "invoke", functionname, "--param-file", jsoninput, "--result"]
		proc = subprocess.Popen(runcode, stdout=subprocess.PIPE)
		stdoutresults = proc.communicate()[0].decode("utf-8")
		jsonoutput = json.dumps(stdoutresults)
		#proc = subprocess.Popen(["rm", "_lambada.log"])
		
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

whiskhttpclienttemplate = """
import subprocess
import requests
import json

userpass = subprocess.check_output("wsk property get --auth", shell=True).split()[2].split(':')
url = ENDPOINT + 'api/v1/namespaces/_/actions/'
"""

whiskproxytemplate = """
def FUNCNAME(PARAMETERSHEAD):
	msg = PACKEDPARAMETERS
	url = "{:s}FUNCNAME_PROVNAME".format(url)
	fullresponse = requests.post(url, json=json.dumps(msg), params={'blocking': 'true', 'result': 'true'}, auth=(userpass[0], userpass[1]))
	response = json.loads(fullresponse.text.read().decode("utf-8"))
	
	return response["ret"]
"""

whiskproxymonadictemplate = """
def FUNCNAME(PARAMETERSHEAD):
	global __lambadalog

	msg = PACKEDPARAMETERS
	url = "{:s}FUNCNAME_PROVNAME".format(url)
	fullresponse = requests.post(url, json=json.dumps(msg), params={'blocking': 'true', 'result': 'true'}, auth=(userpass[0], userpass[1]))
	response = json.loads(fullresponse.text.read().decode("utf-8"))
	
	if "log" in response:
		__lambadalog += response["log"]

	return response["ret"]
"""

whisknetproxytemplate = """
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

def netproxy_handler(args):
	n = Netproxy(args["d"], args["classname"], args["name"], args["args"])
	
	return n
"""

class OpenWhisk(Provider):

    def __init__(self, endpoint=None, role=None):
        super(OpenWhisk, self).__init__(endpoint)
    
    def getTool(self):
        if self.endpoint:
            return "wsk -i --apihost {:s}".format(self.endpoint)
        else:
            return "wsk -i"

    def getCloudFunctions(self):
		#get every function name from action list without namespaces and skipping the first line 
        runcode = "{:s} action list | tail -n +2 | awk \'{{name = split($1, a, \"/\"); print a[name]}}\'".format(self.getTool())
        proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
        stdoutresults = proc.communicate()[0].decode("utf-8")
        cloudfunctions = stdoutresults.strip().split("\n")
        
        return cloudfunctions

    def getTemplate(self):
        return whisktemplate.replace("CLOUDTOOL", ",".join(["\"" + x + "\"" for x in self.getTool().split(" ")]))

    def getName(self):
        return "whisk"

    def getFunctionSignature(self, name):
        return "def {:s}(args):\n".format(name)

    def getMainFilename(self, name):
        return "__main__.py"

    def getCreationString(self, functionname, zipfile, cfc=None):
        runcode = "{:s} action create '{:s}' --kind python:3 --main '{:s}' '{:s}'".format(self.getTool(), functionname, functionname, zipfile.name)
		
        if cfc:
            if cfc.memory:
                runcode += " --memory {}".format(cfc.memory)
            if cfc.duration:
                runcode += " --timeout {}".format(cfc.duration)
        
        return runcode

    def getAddPermissionString(self, name):
        return None

    def getHttpClientTemplate(self):
        template = whiskhttpclienttemplate
        
        if self.endpoint:
            apihost = self.endpoint
        else:
            apihost = subprocess.check_output("{:s} property get --apihost".format(self.getTool()), shell=True).split()[3]
        
        template = template.replace("ENDPOINT", "{:s}".format(apihost))

        return template

    def getArgsVariable(self):
        return "args"

    def getProxyTemplate(self):
        return whiskproxytemplate

    def getProxyMonadicTemplate(self):
        return whiskproxymonadictemplate

    def getNetproxyTemplate(self):
        return whisknetproxytemplate

class IBMCloud(OpenWhisk):

    def __init__(self, endpoint=None, role=None):
        super(IBMCloud, self).__init__(endpoint)
    
    def getTool(self):
        if self.endpoint:
            return "ibmcloud fn --apihost {:s}".format(self.endpoint)
        else:
            return "ibmcloud fn"

    def getCloudFunctions(self):
        return super(IBMCloud, self).getCloudFunctions()

    def getTemplate(self):
        return super(IBMCloud, self).getTemplate()

    def getName(self):
        return "ibmcloud"

    def getFunctionSignature(self, name):
        return super(IBMCloud, self).getFunctionSignature(name)

    def getMainFilename(self, name):
        return super(IBMCloud, self).getMainFilename(name)

    def getCreationString(self, name, zipfile, cfc=None):
        return super(IBMCloud, self).getCreationString(name, zipfile, cfc)

    def getAddPermissionString(self, name):
        return super(IBMCloud, self).getAddPermissionString(name)

    def getHttpClientTemplate(self):
        return super(IBMCloud, self).getHttpClientTemplate()

    def getArgsVariable(self):
        return super(IBMCloud, self).getArgsVariable()

    def getProxyTemplate(self):
        return super(IBMCloud, self).getProxyTemplate()

    def getProxyMonadicTemplate(self):
        return super(IBMCloud, self).getProxyMonadicTemplate()

    def getNetproxyTemplate(self):
        return super(IBMCloud, self).getNetproxyTemplate()

gcloudtemplate = """
def FUNCNAME_remote(args):
	UNPACKPARAMETERS
	FUNCTIONIMPLEMENTATION

def FUNCNAME_stub(jsoninput):
	args = json.loads(jsoninput)
	ret = FUNCNAME_remote(args)
	return json.dumps(ret)

def FUNCNAME(PARAMETERSHEAD):
	local = LOCAL
	jsoninput = json.dumps(PACKEDPARAMETERS)

	if local:
		jsonoutput = FUNCNAME_stub(jsoninput)
	else:
		functionname = "FUNCNAME_PROVNAME"
		runcode = [CLOUDTOOL, "action", "invoke", functionname, "--param-file", jsoninput, "--result"]
		proc = subprocess.Popen(runcode, stdout=subprocess.PIPE)
		stdoutresults = proc.communicate()[0].decode("utf-8")
		jsonoutput = json.dumps(stdoutresults)
		#proc = subprocess.Popen(["rm", "_lambada.log"])
		
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

gcloudhttpclienttemplate = """
import requests

url = "REGION-PROJECT.cloudfunctions.net/"
"""

gcloudproxytemplate = """
def FUNCNAME(PARAMETERSHEAD):
	msg = PACKEDPARAMETERS
	url = "{:s}FUNCNAME_PROVNAME".format(url)
	fullresponse = requests.post(url, data=json.dumps(msg))
	response = json.loads(fullresponse.text.read().decode("utf-8"))
	
	return response["ret"]
"""

gcloudproxymonadictemplate = """
def FUNCNAME(PARAMETERSHEAD):
	global __lambadalog

	msg = PACKEDPARAMETERS
	url = "{:s}FUNCNAME_PROVNAME".format(url)
	fullresponse = requests.post(url, data=json.dumps(msg))
	response = json.loads(fullresponse.text.read().decode("utf-8"))
	
	if "log" in response:
		__lambadalog += response["log"]

	return response["ret"]
"""

gcloudnetproxytemplate = """
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

def netproxy_handler(args):
	n = Netproxy(args["d"], args["classname"], args["name"], args["args"])
	
	return n
"""


class GoogleCloud(Provider):

    def __init__(self, endpoint=None, role=None):
        super(GoogleCloud, self).__init__(endpoint)

        self.region = subprocess.check_output("gcloud config get-value functions/region", shell=True).split()[0]

        if self.region == "(unset)":
            raise Exception("gcloud functions' region not set")

        self.project = subprocess.check_output("gcloud config get-value core/project", shell=True).split()[0]

        if self.project == "(unset)":
            raise Exception("gcloud project not set")
    
    def getTool(self):
        return "gcloud functions"

    def getCloudFunctions(self):
        #get every function name from action list without namespaces and skipping the first line 
        runcode = "{:s} list | tail -n +2 | awk \'{{print($1)}}\'".format(self.getTool())
        proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
        stdoutresults = proc.communicate()[0].decode("utf-8")
        cloudfunctions = stdoutresults.strip().split("\n")

        if(cloudfunctions == ['']):
            cloudfunctions = []
        
        return cloudfunctions

    def getTemplate(self):
        return gcloudtemplate.replace("CLOUDTOOL", ",".join(["\"" + x + "\"" for x in self.getTool().split(" ")]))

    def getName(self):
        return "gcloud"

    def getFunctionSignature(self, name):
        return "def {:s}(request):\n".format(name)

    def getMainFilename(self, name):
        return "main.py"

    def getCreationString(self, functionname, zipfile, cfc=None):
        Zipfile.ZipFile(zipfile).extractall(path="/tmp/{:s}".format(functionname))
        
        runcode = "{:s} deploy  '{:s}' --runtime python37 --entry-point '{:s}' --source '/tmp/{:s}' --trigger-http".format(self.getTool(), functionname, functionname, functionname)
		
        if cfc:
            if cfc.memory:
                runcode += " --memory {}".format(cfc.memory)
            if cfc.duration:
                runcode += " --timeout {}".format(cfc.duration)
        
        return runcode

    def getAddPermissionString(self, name):
        return None

    def getHttpClientTemplate(self):
        template = gcloudhttpclienttemplate
        template = template.replace("REGION", self.region)
        template = template.replace("PROJECT", self.project)
        
        return template

    def getArgsVariable(self):
        return "request"

    def getProxyTemplate(self):
        return whiskproxytemplate

    def getProxyMonadicTemplate(self):
        return whiskproxymonadictemplate

    def getNetproxyTemplate(self):
        return whisknetproxytemplate