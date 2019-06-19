# -*- coding: utf-8 -*-

# Thanks to https://packaging.python.org/tutorials/packaging-projects
import setuptools

with open("README.md", "r") as fh:
	long_description = fh.read()

setuptools.setup(
	name="icinga2api_py",
	version="0.6.5",
	author="TimL20",
	description="Icinga2 API client for Python",
	long_description=long_description,
	long_description_content_type="text/markdown",
	license="BSD 3-Clause License",
	packages=setuptools.find_packages(),
	install_requires=['requests'],
	classifiers=[
		"Programming Language :: Python :: 3",
		"Operating System :: OS Independent",
		"Development Status :: 3 - Alpha",
		"License :: OSI Approved :: BSD License"
	],
)
