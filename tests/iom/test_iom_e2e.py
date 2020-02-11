# -*- coding: utf-8 -*-
"""
End-to-end tests for the IOM part of this library.
"""

import pytest

from ..icinga_mock import mock_session
from ..conftest import REAL_ICINGA

from icinga2api_py.iom.session import Session


URL = "http://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


@pytest.fixture(scope="module")
def mocked_session() -> Session:
	"""Icinga Session (client)."""
	yield from mock_session(Session(URL, **API_CLIENT_KWARGS))


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


# TODO improve the existing tests and add more
