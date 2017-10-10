# Lambada - Command-line parsing

import argparse
import imp
import traceback

from lambadalib import lambada

def execute():
	parser = argparse.ArgumentParser(description='Lambada - Automated Deployment of Python Methods to the (Lambda) Cloud')
	parser.add_argument('modules', metavar='module', type=str, nargs='+', help='module file(s) to move to the cloud')
	parser.add_argument('--local', dest='local', action='store_const', const=True, default=False, help='only local conversion (default: remote deployment)')
	parser.add_argument('--debug', dest='debug', action='store_const', const=True, default=False, help='debugging mode (default: none)')
	parser.add_argument('--endpoint', metavar='ep', type=str, nargs='?', help='service endpoint when not using AWS Lambda but e.g. Snafu')
	parser.add_argument('--annotations', dest='annotations', action='store_const', const=True, default=False, help='only consider decorated functions')

	args = parser.parse_args()

	for module in args.modules:
		basemodule = module.replace(".py", "")
		lambada.printlambada("track module: {:s}".format(basemodule))
		(fileobj, filename, desc) = imp.find_module(basemodule, ["."])
		mod = imp.load_module(basemodule, fileobj, filename, desc)
		fileobj.close()

		try:
			lambada.move(mod.__dict__, local=args.local, module=filename, debug=args.debug, endpoint=args.endpoint, annotations=args.annotations)
		except Exception as e:
			print("Exception: {:s}".format(str(e)))
			if args.debug:
				traceback.print_exc()
			return 1

	return 0
