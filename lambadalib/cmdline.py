# Lambada - Command-line parsing

import argparse
import imp
import traceback

from lambadalib import lambadanew as lambada
from lambadalib import providers as providers

def execute():
	parser = argparse.ArgumentParser(description='Lambada - Automated Deployment of Python Methods to the (Lambda) Cloud')
	parser.add_argument('modules', metavar='module', type=str, nargs='+', help='module file(s) to move to the cloud')
	parser.add_argument('--local', dest='local', action='store_const', const=True, default=False, help='only local conversion (default: remote deployment)')
	parser.add_argument('--debug', dest='debug', action='store_const', const=True, default=False, help='debugging mode (default: none)')
	parser.add_argument('--endpoint', metavar='ep', type=str, nargs='?', help='service endpoint when not using AWS Lambda but e.g. Snafu')
	parser.add_argument('--annotations', dest='annotations', action='store_const', const=True, default=False, help='only consider decorated functions')

	cloudproviders = providers.PROVIDERS
	defaultprovider = providers.DEFAULTPROVIDER
	parser.add_argument('--provider', dest='provider', type=str, choices=cloudproviders, default=defaultprovider, help='Cloud provider: {:s} (default: {:s})'.format(", ".join(cloudproviders), defaultprovider))

	#TODO: Add extra options for each provider and put inside cloudproviderargs
	##e.g. lambdarolearn for aws

	args = parser.parse_args()

	for module in args.modules:
		basemodule = module.replace(".py", "")
		lambada.printlambada("track module: {:s}".format(basemodule))
		(fileobj, filename, desc) = imp.find_module(basemodule, ["."])
		loadedmodule = imp.load_module(basemodule, fileobj, filename, desc)
		fileobj.close()

		try:
			lambada.move(loadedmodule.__dict__, local=args.local, module=filename, debug=args.debug, annotations=args.annotations, cloudprovider=args.provider, cloudproviderargs={"endpoint": args.endpoint})
		except Exception as e:
			print("Exception: {:s}".format(str(e)))
			
			if args.debug:
				traceback.print_exc()
			
			return 1

	return 0
