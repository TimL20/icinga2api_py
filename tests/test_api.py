# -*- coding: utf-8 -*-
"""
Test for layer 1 (request centered layer) of the icinga2api_py library.
"""

import pytest

from icinga2api_py.api import API
from icinga2api_py.models import APIRequest, APIResponse

from .icinga_mock import mock_adapter


URL = "http://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


def test_api_client_init1():
	"""Test basic client init."""
	verify = False
	attr1 = "val1"
	client = API(URL, verify=verify, attr1=attr1)

	assert client.base_url == URL
	assert client.verify == verify
	assert client.attr1 == attr1


def test_api_client_init2():
	"""Test basic client init."""
	host = "icinga"
	verify = False
	attr1 = "val1"

	client = API.from_pieces(host, verify=verify, attr1=attr1)

	assert client.base_url == f"https://{host}:5665/v1/"
	assert client.verify == verify
	assert client.attr1 == attr1


@pytest.fixture
def api_client():
	"""Create the base API client (api.API)."""
	client = API(URL, **API_CLIENT_KWARGS)
	# Adds an adapter for the "icingamock" "protocol"
	mock_adapter(client)
	# Return client with mocked adapter
	return client


def test_request_building(api_client):
	"""Test request building."""
	# TODO parameterize...?
	reqs = (
		"GET", f"{URL}objects/hosts", dict(),
			api_client.objects.hosts.get,
		"GET", f"{URL}objects/hosts", dict(),
			((api_client / "objects") / "hosts") / "get",
		"GET", f"{URL}objects/hosts",dict(),
			api_client.s("objects").s("hosts").s("get"),

		"POST", f"{URL}a/b/c", dict(),
			api_client.a.b.c.post,
	)

	for i in range(0, len(reqs), 4):
		exp_method, exp_url, exp_body, request = reqs[i:(i + 4)]

		# Things, that should be true for every request
		assert request.api == api_client
		assert request.method == "POST"

		# Compare expected and actual values
		assert request.method_override == exp_method
		assert request.url == exp_url
		assert request.json == exp_body


def test_404_paths(api_client):
	"""Test path that should return a 404."""
	# TODO parameterize...?
	responses = (
		api_client.test.whatever.get(),
		api_client.arbitrary.path.post()
	)

	for resp in responses:
		assert resp.status_code == 404


def test_clone(api_client):
	"""Test cloning the API client."""
	clone = api_client.clone(api_client)
	# Basic test for the most crucial things
	assert clone.verify == api_client.verify
	assert clone.auth == api_client.auth
	assert clone.proxies == api_client.proxies
	assert clone.headers == api_client.headers

	# Manipulate clone
	clone.verify = "/path/cert.ca"
	clone.auth = ("abc", "abc")
	clone.proxies = {"test": "abc"}
	clone.headers = {"a": "b"}

	# Check that original api_client hasn't changed
	assert clone.verify != api_client.verify
	assert clone.auth != api_client.auth
	assert clone.proxies != api_client.proxies
	assert clone.headers != api_client.headers
	# Test, that attr1 is not there anymore
	assert not isinstance(clone.attr1, str)
