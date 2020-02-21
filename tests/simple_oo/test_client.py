# -*- coding: utf-8 -*-
"""
Tests for the simple_oo.client module.
"""

import pytest

from ..icinga_mock import mock_session_handler

from icinga2api_py.results import ResultsFromResponse, CachedResultSet
from icinga2api_py.simple_oo.client import Icinga2
from icinga2api_py.simple_oo.base_objects import Icinga2Object, Icinga2Objects

URL = "http://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


@pytest.fixture(scope="module")
def icinga_client():
	"""Icinga client."""
	yield from mock_session_handler(Icinga2(URL, **API_CLIENT_KWARGS))


@pytest.mark.parametrize("req,expected_type", (
		# Objects get
		(("objects", "hosts"), Icinga2Objects),
		# Object get
		(("objects", "hosts", "name"), Icinga2Object),
		# Status is information, but not really an object
		(("status", "IcingaApplication"), CachedResultSet),
		# Everything with /config is not really an object
		(("config", ), ResultsFromResponse),
))
def test_ooquery_decisions(icinga_client, req, expected_type):
	"""Test the decisions of OOQuery per URL."""
	res = icinga_client
	for item in req:
		res = getattr(res, item)
	# One post, one get
	post = res.post()
	res = res.get()
	# Post must always return an ResultsFromResponse
	assert isinstance(post, ResultsFromResponse)
	# For get it's given with the parameters
	assert isinstance(res, expected_type)


def test_create_object(icinga_client):
	"""Test Icinga.create_object()."""
	res = icinga_client.create_object("host", "host123", {})
	assert isinstance(res, ResultsFromResponse)
	assert len(res) == 1
	assert res[0]["code"] == 200
