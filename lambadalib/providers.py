import subprocess
import os
import zipfile as Zipfile

from abc import ABC, abstractmethod
from lambadalib import visitors

PROVIDERS = ['lambda', 'whisk', 'ibm', 'google', 'fission']
DEFAULTPROVIDER = PROVIDERS[0]

def getProvider(provider=DEFAULTPROVIDER, providerargs={}):
    if not provider or provider == PROVIDERS[0]:
        return AWSLambda(providerargs)
    elif provider == PROVIDERS[1]:
        return OpenWhisk(providerargs)
    elif provider == PROVIDERS[2]:
        return IBMCloud(providerargs)
    elif provider == PROVIDERS[3]:
        return GoogleCloud(providerargs)
    elif provider == PROVIDERS[4]:
        return Fission(providerargs)
    else:
        raise Exception("Provider {:s} not supported".format(provider))

def providerPrint(s):
    orange = "\033[33m"
    reset = "\033[0m"
    print(orange, s, reset)
    
class Provider(ABC):

    @abstractmethod
    def __init__(self, providerargs={}):
        self.endpoint = providerargs.get("endpoint")

    @abstractmethod
    def getTool(self):
        pass

    @abstractmethod
    def getCloudFunctions(self):
        pass

    @abstractmethod
    def getTemplate(self):
        pass

    @abstractmethod
    def getProviderName(self):
        pass

    def getFunctionName(self, name):
        return "{:s}_{:s}".format(name, self.getProviderName())

    @abstractmethod
    def getFunctionSignature(self, name):
        pass

    @abstractmethod
    def getMainFilename(self, name):
        pass

    @abstractmethod
    def getCreationString(self, functionname, zipfile, cloudfunctionconfig=None):
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

    @abstractmethod
    def getNodeVisitor(self, functions, annotations):
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

    def __init__(self, providerargs={}):
        super(AWSLambda, self).__init__(providerargs)
        self.lambdarolearn = providerargs.get("role")

    def getTool(self):
        if self.endpoint:
            return "aws --endpoint-url {:s}".format(self.endpoint)
        else:
            return "aws"

    def getCloudFunctions(self):
        runcode = "{:s} lambda list-functions | grep FunctionName | cut -d '\"' -f 4".format(self.getTool())
        proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
        stdoutresults = proc.communicate()[0].decode("utf-8")
        cloudfunctions = stdoutresults.strip().split("\n")
        
        return cloudfunctions

    def getTemplate(self):
        return awstemplate.replace("CLOUDTOOL", ",".join(["\"" + x + "\"" for x in self.getTool().split(" ")]))

    def getProviderName(self):
        return "lambda"

    def getFunctionSignature(self, name):
        return "def {:s}(event, context):\n".format(name)

    def getMainFilename(self, name):
        return "{:s}.py".format(name)

    def setRole(self):
        LAMBDAROLEANRLENGTH = 12
        
        if not self.lambdarolearn:
            providerPrint("Role not set, trying to read environment variable LAMBDAROLEARN")
            self.lambdarolearn = os.getenv("LAMBDAROLEARN")
		    
            if not self.lambdarolearn:
                providerPrint("Environment variable not set, trying to assemble...")
                runcode = "{} sts get-caller-identity --output text --query 'Account'".format(self.getTool())
                proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
                stdoutresults = proc.communicate()[0].decode("utf-8").strip()
			    
                if len(stdoutresults) == LAMBDAROLEANRLENGTH:
                    self.lambdarolearn = "arn:aws:iam::{:s}:role/lambda_basic_execution".format(stdoutresults)
                    providerPrint("... assembled {:s}".format(self.lambdarolearn))
                    
                if not self.lambdarolearn:
                    raise Exception("Role not set - check lambdarolearn=... or LAMBDAROLEARN=...")

    def getCreationString(self, functionname, zipfile, cloudfunctionconfig=None):
        self.setRole()

        runcode = "{:s} lambda create-function --function-name '{:s}' --description 'Lambada remote function' --runtime 'python3.6' --role '{:s}' --handler '{:s}.{:s}' --zip-file 'fileb://{:s}'".format(self.getTool(), functionname, self.lambdarolearn, functionname, functionname, zipfile.name)
		
        if cloudfunctionconfig:
            if cloudfunctionconfig.memory:
                runcode += " --memory-size {}".format(cloudfunctionconfig.memory)
            if cloudfunctionconfig.duration:
                runcode += " --timeout {}".format(cloudfunctionconfig.duration)
        
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

    def getNodeVisitor(self, functions, annotations):
        return visitors.FuncListener(functions, annotations)

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

    def __init__(self, providerargs={}):
        super(OpenWhisk, self).__init__(providerargs)
    
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

    def getProviderName(self):
        return "whisk"

    def getFunctionSignature(self, name):
        return "def {:s}(args):\n".format(name)

    def getMainFilename(self, name):
        return "__main__.py"

    def getCreationString(self, functionname, zipfile, cloudfunctionconfig=None):
        runcode = "{:s} action create '{:s}' --kind python:3 --main '{:s}' '{:s}'".format(self.getTool(), functionname, functionname, zipfile.name)
		
        if cloudfunctionconfig:
            if cloudfunctionconfig.memory:
                runcode += " --memory {}".format(cloudfunctionconfig.memory)
            if cloudfunctionconfig.duration:
                runcode += " --timeout {}".format(cloudfunctionconfig.duration)
        
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

    def getNodeVisitor(self, functions, annotations):
        return visitors.FuncListener(functions, annotations)

class IBMCloud(OpenWhisk):

    def __init__(self, providerargs={}):
        super(IBMCloud, self).__init__(providerargs)
    
    def getTool(self):
        if self.endpoint:
            return "ibmcloud fn --apihost {:s}".format(self.endpoint)
        else:
            return "ibmcloud fn"

    def getProviderName(self):
        return "ibmcloud"

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

    def __init__(self, providerargs={}):
        super(GoogleCloud, self).__init__(providerargs)

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

    def getProviderName(self):
        return "gcloud"

    def getFunctionSignature(self, name):
        return "def {:s}(request):\n".format(name)

    def getMainFilename(self, name):
        return "main.py"

    def getCreationString(self, functionname, zipfile, cloudfunctionconfig=None):
        Zipfile.ZipFile(zipfile).extractall(path="/tmp/{:s}".format(functionname))
        
        runcode = "{:s} deploy  '{:s}' --runtime python37 --entry-point '{:s}' --source '/tmp/{:s}' --trigger-http".format(self.getTool(), functionname, functionname, functionname)
		
        if cloudfunctionconfig:
            if cloudfunctionconfig.memory:
                runcode += " --memory {}".format(cloudfunctionconfig.memory)
            if cloudfunctionconfig.duration:
                runcode += " --timeout {}".format(cloudfunctionconfig.duration)
        
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
        return gcloudproxytemplate

    def getProxyMonadicTemplate(self):
        return gcloudproxymonadictemplate

    def getNetproxyTemplate(self):
        return gcloudnetproxytemplate

    def getNodeVisitor(self, functions, annotations):
        return visitors.FuncListenerGCloud(functions, annotations)

fissiontemplate = """
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
		runcode = [CLOUDTOOL, "test", "--name", functionname, "--body", jsoninput]
		proc = subprocess.Popen(runcode, stdout=subprocess.PIPE)
		stdoutresults = proc.communicate()[0].decode("utf-8")
		jsonoutput = json.dumps(stdoutresults)
		#proc = subprocess.Popen(["rm", "_lambada.log"])
		
		if "errorMessage" in jsonoutput:
			raise Exception("Fission Remote Issue: {:s}; runcode: {:s}".format(jsonoutput, " ".join(runcode)))

	output = json.loads(jsonoutput)
	
	if "log" in output:
		if local:
			if output["log"]:
				print(output["log"])
		else:
			lambada.lambadamonad(output["log"])

	return output["ret"]
"""

fissionhttpclienttemplate = """
import requests

url = "FISSION_ROUTER/"
"""

fissionproxytemplate = """
def FUNCNAME(PARAMETERSHEAD):
	msg = PACKEDPARAMETERS
	url = "{:s}FUNCNAME_PROVNAME".format(url)
	fullresponse = requests.post(url, data=json.dumps(msg))
	response = json.loads(fullresponse.text.read().decode("utf-8"))
	
	return response["ret"]
"""

fissionproxymonadictemplate = """
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

fissionnetproxytemplate = """
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


class Fission(Provider):

    def __init__(self, providerargs={}):
        super(Fission, self).__init__(providerargs)

        #TODO get user-set evironment
        self.router = providerargs.get("endpoint")
    
    def getTool(self):
        return "fission function"

    def getCloudFunctions(self):
        #get every function name from function list without namespaces and skipping the first line 
        runcode = "{:s} list | tail -n +2 | awk \'{{print($1)}}\'".format(self.getTool())
        proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
        stdoutresults = proc.communicate()[0].decode("utf-8")
        cloudfunctions = stdoutresults.strip().split("\n")

        if(cloudfunctions == ['']):
            cloudfunctions = []
        
        return cloudfunctions

    def getTemplate(self):
        return fissiontemplate.replace("CLOUDTOOL", ",".join(["\"" + x + "\"" for x in self.getTool().split(" ")]))

    def getProviderName(self):
        return "fission"

    def getFunctionName(self, name):
        return "{:s}-{:s}".format(name, self.getProviderName())

    def getFunctionSignature(self, name):
        #return "def {:s}():\n".format(name)
        return "def main():\n"

    def getMainFilename(self, name):
        return "{:s}-fission.py".format(name)

    def setRouter(self):
        IPLENGTH = 15
        PORTLENGTH = 5

        if not self.router:
            providerPrint("Router not set, trying to read environment variable FISSION_ROUTER")
            self.router = os.getenv("FISSION_ROUTER")

            if not self.router:
                providerPrint("Environment variable not set, trying to get minikube's ip")
                runcode = "minikube ip"
                proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
                stdoutresults = proc.communicate()[0].decode("utf-8").strip()
                
                if len(stdoutresults) <= IPLENGTH:
                    ip = "{:s}".format(stdoutresults)
                    
                    runcode = "kubectl -n fission get svc router -o jsonpath='{...nodePort}'"
                    proc = subprocess.Popen(runcode, stdout=subprocess.PIPE, shell=True)
                    stdoutresults = proc.communicate()[0].decode("utf-8").strip()

                    if len(stdoutresults) <= PORTLENGTH:
                        port = "{:s}".format(stdoutresults)
                        self.router = "{:s}:{:s}".format(ip, port)

                if not self.router:
                    raise Exception("Router not set - check endpoint or FISSION_ROUTER")

    def getCreationString(self, functionname, zipfile, cloudfunctionconfig=None):
        self.setRouter()

        Zipfile.ZipFile(zipfile).extractall(path="/tmp/{:s}".format(functionname))
        
        runcode = "{:s} create --name '{:s}' --env python --code '/tmp/{:s}/{:s}.py'".format(self.getTool(), functionname, functionname, functionname)
		
        if cloudfunctionconfig:
            if cloudfunctionconfig.memory:
                runcode += " --maxmemory {}".format(cloudfunctionconfig.memory)
            if cloudfunctionconfig.duration:
                runcode += " --fntimeout {}".format(cloudfunctionconfig.duration)

        runcode += " && fission route create --function {:s} --url /{:s}".format(functionname, functionname)
        
        return runcode

    def getAddPermissionString(self, name):
        return None

    def getHttpClientTemplate(self):
        self.setRouter()

        template = fissionhttpclienttemplate.replace("FISSION_ROUTER", self.router)
        
        return template

    def getArgsVariable(self):
        return "request.get_json()"

    def getProxyTemplate(self):
        return fissionproxytemplate

    def getProxyMonadicTemplate(self):
        return fissionproxymonadictemplate

    def getNetproxyTemplate(self):
        return fissionnetproxytemplate

    def getNodeVisitor(self, functions, annotations):
        return visitors.FuncListenerGCloud(functions, annotations)
