# -*- coding: utf-8 -*-
"""
Tests for the iom.session module.
"""

import pytest

from ..icinga_mock import mock_session

from icinga2api_py.models import APIResponse
from icinga2api_py.results import CachedResultSet
from icinga2api_py.iom import Session
from icinga2api_py.iom.complex_types import IcingaConfigObjects, IcingaConfigObject


URL = "http://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


@pytest.fixture(scope="module")
def iom_session():
	"""Icinga client."""
	session = Session(URL, **API_CLIENT_KWARGS)
	mock_session(session)
	# Types object is already created at this point and therefore would remain "unmocked"
	mock_session(session.types.request.api)
	with session:
		yield session


@pytest.mark.parametrize("req,expected_type", (
		# Objects get
		(("objects", "hosts"), IcingaConfigObjects),
		# Object get
		(("objects", "hosts", "name"), IcingaConfigObject),
		# Status is information, but not really an object
		(("status", "IcingaApplication"), CachedResultSet),
		# config, console, ... are special cases, behavior for these is currently not specified
))
def test_iomquery_decisions(iom_session, req, expected_type):
	"""Test the decisions of OOQuery per URL."""
	res = iom_session
	for item in req:
		res = getattr(res, item)
	# One post, one get
	post = res.post()
	res = res.get
	res = res()
	# Post must always return an APIResponse
	assert isinstance(post, APIResponse)
	# For get it's given with the parameters
	assert isinstance(res, expected_type)
