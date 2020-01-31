# -*- coding: utf-8 -*-
"""
General test configuration/setup.
"""

import json
import pytest


# Connection to a real Icinga instance to test with; this is set with the CLI parameter --icinga
REAL_ICINGA = {
	# True to enable tests with a real Icinga instance, is automatically set if the --icinga CLI option is provided
	"usage": False,
	# URL for this instance
	"url": "https://icinga:5665/v1/",
	# Session parameters, e.g. verify, auth, proxies, ...
	"sessionparams": {
		"auth": ("user", "pass"),
	}
}


def pytest_addoption(parser):
	parser.addoption(
		"--icinga", default="",
		help="Configure to run tests with a real Icinga instance, JSON-encoded. "
			+ "Example: \n"
			+ '{"url": "https://icinga:5665/v1/", "sessionparams": {"auth": ["user", "pass"]}}'
	)


def pytest_configure(config):
	# Register "real" mark
	config.addinivalue_line("markers", "real: for testing with a real icinga instance")

	# Configure real Icinga if set
	icinga = config.getoption("--icinga").strip()
	if icinga:
		REAL_ICINGA["usage"] = True
		REAL_ICINGA.update(json.loads(icinga))
		# Special case: JSON doesn't know tuples, but requests expects tuples for HTTP basic auth
		if "auth" in REAL_ICINGA["sessionparams"]:
			REAL_ICINGA["sessionparams"]["auth"] = tuple(REAL_ICINGA["sessionparams"]["auth"])


def pytest_collection_modifyitems(items):
	# Add skip mark to tests marked with real
	skip_real = pytest.mark.skip(reason="Skipping tests with a real Icinga instance")
	for item in items:
		if "real" in item.keywords:
			item.add_marker(skip_real)
