# -*- coding: utf-8 -*-

# Thanks to https://packaging.python.org/tutorials/packaging-projects
# And https://github.com/pallets/flask/blob/master/setup.py
from setuptools import setup
import re

# Read the __version__ string from the __init__ file to avoid changing it here all the time
with open("icinga2api_py/__init__.py", "rt") as file:
	version = re.search(r'__version__ = "(.*?)"', file.read()).group(1)

with open("README.md", "r") as fh:
	long_description = fh.read()

setup(
	name="icinga2api_py",
	version=version,
	author="Tim Lehner",
	description="Icinga2 API client for Python",
	long_description=long_description,
	long_description_content_type="text/markdown",
	license="BSD 3-Clause License",
	packages=["icinga2api_py"],
	python_requires=">=3.5",
	install_requires=['requests'],
	tests_require=['requests', 'pytest'],
	extras_require={
		"test": ["pytest"],
		"doc": ["Sphinx"],
	},
	classifiers=[
		"Programming Language :: Python :: 3",
		"Operating System :: OS Independent",
		"Development Status :: 3 - Alpha",
		"License :: OSI Approved :: BSD License",
		"Intended Audience :: Developers",
	],
	keywords="icinga2 api library",
	url="https://github.com/TimL20/icinga2api_py",
	project_urls={
		"Source": "https://github.com/TimL20/icinga2api_py",
		"Bug Reports": "https://github.com/TimL20/icinga2api_py/issues",
	},
)
