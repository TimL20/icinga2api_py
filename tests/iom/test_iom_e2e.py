# -*- coding: utf-8 -*-
"""
End-to-end tests for the IOM part of this library.
"""

import pytest

from ..icinga_mock import mock_session
from ..conftest import REAL_ICINGA

from icinga2api_py.iom.session import Session
from icinga2api_py.iom.exceptions import NoUserModify


URL = "http://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


@pytest.fixture(scope="module")
def mocked_session() -> Session:
	"""Icinga Session (client)."""
	session = Session(URL, **API_CLIENT_KWARGS)
	mock_session(session)
	# Types object is already created at this point and therefore would remain "unmocked"
	mock_session(session.types.request.api)
	with session:
		yield session


@pytest.fixture(scope="module", params=["mocked", pytest.param("real", marks=pytest.mark.real)])
def session(request, mocked_session) -> Session:
	"""Create the base API client (api.API), with a mocked or/and a real Icinga instance."""
	if request.param == "mocked":
		# Test with the mocked Icinga instance
		yield mocked_session
		return
	else:
		# Test with a real Icinga instance
		client = Session(REAL_ICINGA["url"], **REAL_ICINGA["sessionparams"])
	# With makes sure the session is closed
	with client:
		yield client


def test_hosts1(session):
	"""Simple test case: One host gets queried."""
	host = session.objects.hosts.localhost.get()
	assert host.name == "localhost"
	assert host.state in (0, 1)


def test_hosts2(session):
	"""Some hosts get queried."""
	hosts = session.objects.hosts.get()
	# We assume that Icinga always knows at least one host...
	assert len(hosts) > 0

	host0 = hosts[0]
	assert host0.state in (0, 1)


def test_modify1(session):
	"""Test IcingaConfigObject modification for one object."""
	obj = session.objects.hosts.localhost.get()
	value = "b" if obj.notes == "a" else "a"
	# Modify the object
	obj.notes = value
	# Check that the object itself was modified
	assert obj.notes == value

	# Query the object again to check that the modification was flushed
	obj = session.objects.hosts.localhost.get()
	assert obj.notes == value

	# Test that NoUserModify is raised for this very simple case
	with pytest.raises(NoUserModify):
		obj.name = "abc"


def test_modify2a(session):
	"""Test IcingaConfigObject dictionary modification for one object."""
	obj = session.objects.hosts.localhost.get()
	val1 = 2 if getattr(obj.vars, "val1", 1) == 1 else 1

	# Modify the object
	obj.vars.val1 = val1
	# Check, that the object itself was modified
	assert obj.vars.val1 == val1

	# Query the object again to check that the modification was flushed
	obj = session.objects.hosts.localhost.get()
	assert obj.vars.val1 == val1


def test_modify2b(session):
	"""Test IcingaConfigObject modification with multiple modifications sequentially."""
	obj = session.objects.hosts.localhost.get()
	val1 = 2 if getattr(obj.vars, "val1", 1) == 1 else 1
	val2 = 2 if getattr(obj.vars, "val2", 1) == 1 else 1

	# Modify the object
	obj.vars.val1 = val1
	obj.vars.val2 = val2
	# Check, that the object itself was modified
	assert obj.vars.val1 == val1
	assert obj.vars.val2 == val2

	# Query the object again to check that the modification was flushed
	obj = session.objects.hosts.localhost.get()
	assert obj.vars.val1 == val1
	assert obj.vars.val2 == val2


def test_modify3(session):
	"""Test IcingaConfigObject modification with multiple modifications."""
	obj = session.objects.hosts.localhost.get()
	val1 = 2 if getattr(obj.vars, "val1", 1) == 1 else 1
	val2 = 2 if getattr(obj.vars, "val2", 1) == 1 else 1

	# Modify the object
	obj.modify({"vars.val1": val1, "vars.val2": val2})
	# Check, that the object itself was modified
	assert obj.vars.val1 == val1
	assert obj.vars.val2 == val2

	# Query the object again to check that the modification was flushed
	obj = session.objects.hosts.localhost.get()
	assert obj.vars.val1 == val1
	assert obj.vars.val2 == val2


# TODO improve the existing tests and add more
