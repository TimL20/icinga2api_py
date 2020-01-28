# -*- coding: utf-8 -*-
"""
General test configuration/setup.
"""

import json
import pytest


# Connection to a real Icinga instance to test with
# To set with CLI parameter --icinga
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

skip_real = pytest.mark.skipif(not REAL_ICINGA["usage"], reason="Skipping tests with a real Icinga instance")


def pytest_addoption(parser):
	parser.addoption(
		"--icinga", default="",
		help="Configure to run tests with a real Icinga instance, JSON-encoded. "
			+ "Example: \n"
			+ '{"url": "https://icinga:5665/v1/", "sessionparams": {"auth": ["user", "pass"]}}'
	)


def pytest_configure(config):
	# Configure real Icinga if set
	icinga = config.getoption("--icinga").strip()
	if icinga:
		REAL_ICINGA["usage"] = True
		REAL_ICINGA.update(json.loads(icinga))
		# Special case: JSON doesn't know tuples, but requests expects tuples for HTTP basic auth
		if "auth" in REAL_ICINGA["sessionparams"]:
			REAL_ICINGA["sessionparams"]["auth"] = tuple(REAL_ICINGA["sessionparams"]["auth"])
		# Override skip_real mark
		global skip_real
		skip_real = pytest.mark.skipif(not REAL_ICINGA["usage"], reason="Skipping tests with a real Icinga instance")
