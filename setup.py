# python3 setup.py sdist
# python3 setup.py bdist_wheel
# python3 setup.py bdist_egg
# twine upload dist/*.* [-r testpypi]

from setuptools import setup
import os

setup(
	name="lambadatransformer",
	description="Lambada - Automated Deployment of Python Methods to the (Lambda) Cloud",
	version="0.0.1",
	url="https://gitlab.com/josefspillner/lambada.git",
	author="Josef Spillner",
	author_email="josef.spillner@zhaw.ch",
	license="AGPL 3.0",
	classifiers=[
		"Development Status :: 2 - Pre-Alpha",
		"Environment :: Console",
		"Intended Audience :: Science/Research",
		"License :: OSI Approved :: GNU Affero General Public License v3",
		"Programming Language :: Python :: 3",
		"Topic :: Software Development :: Code Generators"
	],
	keywords="cloud faas serverless functions",
	packages=["lambadalib"],
	scripts=["lambada"]
)
