# -*- coding: utf-8 -*-
"""
Test for layer 1 (request centered layer) of the icinga2api_py library.
"""

from collections.abc import Sequence, Mapping
import pytest

from .icinga_mock import mock_adapter
from .conftest import REAL_ICINGA

from icinga2api_py.api import API
from icinga2api_py.models import APIRequest


URL = "mock://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


#######################################################################################################################
# Test basic client init
#######################################################################################################################


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


#######################################################################################################################
# API client fixtures: mocked only / mocked and real
#######################################################################################################################


@pytest.fixture(scope="module")
def mocked_api_client() -> API:
	"""Create a base API client with a mocked Icinga instance (only)."""
	client = API(URL, **API_CLIENT_KWARGS)
	# Adds a custom adapter for "mock://"
	mock_adapter(client)
	# With makes sure the session is closed
	with client:
		yield client


@pytest.fixture(scope="module", params=["mocked", pytest.param("real", marks=pytest.mark.real)])
def api_client(request, mocked_api_client) -> API:
	"""Create the base API client (api.API), with a mocked or/and a real Icinga instance."""
	if request.param == "mocked":
		# Test with the mocked Icinga instance
		yield mocked_api_client
		return
	else:
		# Test with a real Icinga instance
		client = API(REAL_ICINGA["url"], **REAL_ICINGA["sessionparams"])
	# With makes sure the session is closed
	with client:
		yield client


#######################################################################################################################
# Test the API client
#######################################################################################################################


def test_prepare_base_url():
	"""Test API.prepare_base_url(url)."""
	# It doesn't matter what comes out, but it all has to be the same...
	urls = {
		API.prepare_base_url("icinga"),
		API.prepare_base_url("icinga:5665"),
		API.prepare_base_url("https://icinga"),
		API.prepare_base_url("https://icinga:5665"),
		API.prepare_base_url("https://icinga/v1"),
		API.prepare_base_url("https://icinga:5665/v1"),
		API.prepare_base_url("https://icinga/v1/"),
		API.prepare_base_url("icinga/v1/"),
		API.prepare_base_url("icinga/v1"),
	}
	# Debug output
	print(urls)
	assert len(urls) == 1


class TestAPIRequest:
	"""Tests for APIRequests."""

	EXAMPLE_REQUESTS_LENGTH = 11

	@staticmethod
	def generate_example_requests(api_client, url):
		"""Generate example requests."""
		return (
			"GET", f"{url}objects/hosts", dict(),
				api_client.objects.hosts.get,
			"GET", f"{url}objects/hosts", dict(),
				api_client / "objects" / "hosts" / "get",
			"GET", f"{url}objects/hosts", dict(),
				api_client.s("objects").s("hosts").s("get"),

			"POST", f"{url}a/b/c", dict(),
				api_client.a.b.c.post,

			"POST", f"{url}a/b", {"key": "value"},
				api_client.a.b.key("value").post,
			"POST", f"{url}a/b", dict(),
				api_client.a.b.key("value").key().post,

			"POST", f"{url}a/b", {"key": ["value1", "value2"]},
				api_client.a.b.key("value1", "value2").post,
			"POST", f"{url}a/b", {"key": ["value1", "value2"]},
				api_client.a.b.key("value1").key("value2").post,

			"POST", f"{url}a/b", {"key": ["value1", "value2", "value3"]},
				api_client.a.b.key("value1", "value2").key("value3").post,
			"POST", f"{url}a/b", {"key": ["value1", "value2", "value3"]},
				api_client.a.b.key("value1").key("value2", "value3").post,

			"POST", f"{url}a/b", {"key": ["value1", "value2", "value3", "value4"]},
				api_client.a.b.key("value1", "value2").key("value3", "value4").post,

			# Adjusting this may need to adjust the EXAMPLE_REQUESTS_LENGTH
			# 	Because the length of this is required before it actually is built
		)

	def example_request(self, api_client, url, i):
		"""Returns a tuple of (expected method, expected URL, expected body, request)."""
		if not hasattr(self, "example_requests"):
			self.example_requests = self.generate_example_requests(api_client, url)
		return self.example_requests[i * 4:i * 4 + 4]

	@pytest.mark.parametrize("i", [i for i in range(EXAMPLE_REQUESTS_LENGTH)])
	def test_request_building(self, api_client, i):
		"""Test request building."""
		url = api_client.base_url
		exp_method, exp_url, exp_body, request = self.example_request(api_client, url, i)

		# Things, that should be true for every request
		assert request.api == api_client
		assert request.method == "POST"

		# Compare expected and actual values
		assert request.method_override == exp_method
		assert request.url == exp_url
		assert request.json == exp_body


def test_404_paths(api_client):
	"""Test paths that should return a 404 error code."""
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


#######################################################################################################################
# Test models.APIRequest
#######################################################################################################################


def test_request(mocked_api_client):
	"""Test models.APIRequest general things."""
	request = APIRequest(api_client)
	method = "GET"
	request2 = APIRequest(api_client, method, URL)

	assert request != request2
	assert request.method == "POST"
	assert request2.method == "POST"
	assert request2.method_override == method
	assert request2.url == URL

	request.method_override = method
	assert request.method_override == method
	request.url = URL
	# Test APIRequest.__eq__()
	assert request == request2


def test_request_clone(mocked_api_client):
	"""Test models.APIRequest.clone() method."""
	method = "GET"
	headers = {"abc": "def", "ghi": "jkl"}
	request = APIRequest(mocked_api_client, method, URL, headers=headers)
	clone = request.clone()
	assert request == clone

	# Manipulate things and see whether the original changes
	clone.method_override = "POST"
	assert request.method_override == method
	clone.headers.update({"abc": "abc"})
	assert request.headers == headers


def test_request_envmerge(mocked_api_client, monkeypatch):
	"""Test environment settings merge (proxies, ...) in APIRequest."""
	proxy = "https://localhost:8080"

	# The environment settings are only used when the request is sent...
	# The mock adapter has a settings hook, otherwise checking the settings would be a pain...

	def settings_hook(**settings):
		assert settings["proxies"].get("mock") == proxy

	# Clone the client to avoid harm for others
	mocked_api_client = mocked_api_client.clone(mocked_api_client)
	# Make sure a "mock" proxy is not set
	mocked_api_client.proxies.pop("mock", None)
	# Set the settings hook
	mock_adapter(mocked_api_client, settings_hook=settings_hook)

	# Monkey patching environment variables for testing
	monkeypatch.setenv("MOCK_PROXY", proxy)
	# The settings hook will do the assert
	mocked_api_client.status.get()


#######################################################################################################################
# Test models.APIRequest
#######################################################################################################################


class ExampleResponses:
	def __init__(self, api_client):
		# The pytest parameterize mark would be better, but that seems not to be possible as the api_client is used here
		self.e404 = api_client.test.path.get()
		self.localhost = api_client.objects.hosts.localhost.get()
		self.hosta = api_client.objects.hosts.hosta.get()


@pytest.fixture
def responses(api_client):
	"""Generate some example responses."""
	return ExampleResponses(api_client)


def test_response_eq(api_client):
	"""Test the equality test for APIResponse objects."""
	resp1 = ExampleResponses(api_client)
	resp2 = ExampleResponses(api_client)

	# Test equality
	assert resp1.e404 == resp2.e404
	assert resp1.localhost == resp2.localhost

	# Test not equal
	assert resp1.e404 != resp1.localhost
	assert resp1.localhost != resp1.hosta


def test_response_results(responses):
	"""Test APIResponse.json()"""
	assert isinstance(responses.localhost.json(), Mapping)

	assert isinstance(responses.localhost.results(), Sequence)
	assert len(responses.e404.results()) == 0
