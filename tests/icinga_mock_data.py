# -*- coding: utf-8 -*-
"""
Data for icinga_mock.
"""

import base64
import json

# Defaults
DEFAULTS = {
	"auth": f"Basic {base64.b64encode(b'user:pass').decode('utf-8')}"  # "Basic dXNlcjpwYXNz"
}

# Errors
ERRORS = {
	400: {
		"reason": "Bad request"
	},
	401: {
		"reason": "Unauthorized",
		"headers": {"WWW-Authenticate": "Basic realm=\"Icinga 2\""},
	},
	404: {
		"reason": "No such path for mocked Icinga instance",
		"body": json.dumps({
			"error":404,
			"status":"The requested path 'v1/bla/bla' could not be found for mocked Icinga."
		}),
	},
}


def get_error(status_code):
	err = ERRORS.get(status_code, dict())
	err["status_code"] = status_code
	return err
