# -*- coding: utf-8 -*-
"""
Test the clients module.
"""

from collections.abc import Mapping, Sequence
import pytest

from .icinga_mock import mock_session
from .conftest import REAL_ICINGA
from .test_api import ExampleResponses

from icinga2api_py.clients import Client, StreamClient
from icinga2api_py.models import APIRequest, APIResponse


URL = "mock://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


def fake_request_accepting_class(request):
	"""Fake a class that accepts a request parameter."""
	return request


def fake_response_accepting_class(response):
	"""Fake a class that accepts a response parameter."""
	return response


@pytest.fixture(scope="module")
def request_client():
	"""Client returning the request on request handling."""
	yield from mock_session(Client(URL, results_class=fake_request_accepting_class, **API_CLIENT_KWARGS))


@pytest.fixture(scope="module")
def response_client():
	"""Client returning the request on request handling."""
	yield from mock_session(Client(URL, results_class=fake_response_accepting_class, **API_CLIENT_KWARGS))


@pytest.fixture(scope="module", params=["mocked", pytest.param("real", marks=pytest.mark.real)])
def stream_client(request):
	"""Client returning the request on request handling."""
	if request.param == "mocked":
		yield from mock_session(StreamClient(URL, **API_CLIENT_KWARGS))
	else:
		client = StreamClient(REAL_ICINGA["url"], **REAL_ICINGA["sessionparams"])
		# With makes sure the session is closed
		with client:
			yield client


def test_client_request(request_client):
	"""Test that the client correctly inits the "results class" with a request."""
	req0 = request_client.a.b.get
	# Because of the fake_request_accepting_class this should be exactly the same...
	req1 = request_client.a.b.get()
	assert isinstance(req1, APIRequest)
	assert req1 == req0


def test_client_response(response_client):
	"""Test that the client correctly inits the "results class" with a response."""
	responses = ExampleResponses(response_client)
	assert responses.e404.status_code == 404
	assert len(responses.e404.results()) == 0
	assert isinstance(responses.e404, APIResponse)
	assert isinstance(responses.localhost.json(), Mapping)
	assert isinstance(responses.localhost.results(), Sequence)


#######################################################################################################################
# StreamClient
#######################################################################################################################

def test_stream_client(stream_client):
	"""Test the StreamClient."""
	type_ = "CheckResult"
	with stream_client.events.types([type_]).queue("abcdefg").post() as stream:
		i = 0
		for res in stream:
			# Icinga sets the type, as well as the mocked Icinga
			assert res["type"] == type_
			i += 1
			if i > 2:
				break
