import subprocess
import os

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
    def getCreationString(self, name, zipfile, cfc=None):
        pass
    
    @abstractmethod
    def getAddPermissionString(self, name):
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
		functionname = "FUNCNAME_lambda"
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

    def getCreationString(self, name, zipfile, cfc=None):

        self.setRole()

        runcode = "{:s} lambda create-function --function-name '{:s}' --description 'Lambada remote function' --runtime 'python3.6' --role '{:s}' --handler '{:s}.{:s}' --zip-file 'fileb://{:s}'".format(self.getTool(), name, self.lambdarolearn, name, name, zipfile)
		
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

whisktemplate = """
def FUNCNAME_remote(event):
	UNPACKPARAMETERS
	FUNCTIONIMPLEMENTATION

def FUNCNAME_stub(jsoninput):
	event = json.loads(jsoninput)
	ret = FUNCNAME_remote(event)
	return json.dumps(ret)

def FUNCNAME(PARAMETERSHEAD):
	local = LOCAL
	jsoninput = json.dumps(PACKEDPARAMETERS)
	if local:
		jsonoutput = FUNCNAME_stub(jsoninput)
	else:
		functionname = "FUNCNAME_whisk"
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
        return "def {:s}(event):\n".format(name)

    def getMainFilename(self, name):
        return "__main__.py"

    def getCreationString(self, name, zipfile, cfc=None):
        runcode = "{:s} action create '{:s}' --kind python:3 --main '{:s}' '{:s}'".format(self.getTool(), name, name, zipfile)
		
        if cfc:
            if cfc.memory:
                runcode += " --memory {}".format(cfc.memory)
            if cfc.duration:
                runcode += " --timeout {}".format(cfc.duration)
        
        return runcode

    def getAddPermissionString(self, name):
        return None

