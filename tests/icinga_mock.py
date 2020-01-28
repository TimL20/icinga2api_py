# -*- coding: utf-8 -*-
"""
This module provides a mocked "Icinga" to communicate with.

It's quite dirty, but should do its work for the tests...
"""

from collections import OrderedDict
from io import BytesIO
import json

from requests import Session
from requests.adapters import BaseAdapter
from requests.models import PreparedRequest, Response
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from requests.exceptions import ConnectionError
from urllib.parse import urlparse

from .icinga_mock_data import DEFAULTS, get_error, OBJECTS


def get_method(request: PreparedRequest):
	"""Get method or X-HTTP-Method-Override."""
	return request.headers.get("X-HTTP-Method-Override", None) or request.method


def list_elongation(lst, length, value=None):
	"""Append value to lst as long as length is not reached, return lst."""
	for i in range(len(lst), length):
		lst.append(value)
	return lst


def get_path_splited(url, min_items=0, max_items=99):
	"""Get a list of the URL path split at '/', with checks for minimum and maximum path items (and None as default)."""
	splited = urlparse(url).path.split('/', max_items-1)
	if len(splited) < min_items:
		raise ValueError("Too few URL path items")

	return list_elongation(splited, max_items)


class Icinga:
	"""A fake Icinga "instance" for testing without a real Icinga."""

	ATTRS = ("auth", )

	def __init__(self, **kwargs):
		for attr in self.ATTRS:
			# Get attribute value from kwargs, default to icinga_mock_data defaults
			setattr(self, attr, kwargs.get(attr, DEFAULTS.get(attr)))

	def handle(self, request: PreparedRequest):
		"""Entrypoint ot handle a request."""
		response = self._handle(request)
		# Do things that appear for every response and defaults, if not explicitely overwritten
		# Default body
		response.setdefault("body", "")
		# Default status code
		response.setdefault("status_code", 200)
		# Headers
		response.setdefault("headers", dict())
		headers = response["headers"]
		# Content type
		if response["status_code"] >= 400:
			headers.setdefault("Content-Type", "text/html")
		else:
			headers.setdefault("Content-Type", "application/json")
		# Transfer encoding
		headers.setdefault("Transfer-Encoding", "chunked")
		# Server
		headers.setdefault("Server", "Icinga_mock/r2.10.4-1")

		return response

	def _handle(self, request: PreparedRequest):
		"""Handle a request."""
		response = self.check_headers(request)
		if response:
			return response

		_, version, path, subpath = get_path_splited(request.url, 3, 4)
		if version != "v1":
			raise ValueError("Invalid API version")

		handler = getattr(self, path, None)
		if handler:
			# Let exceptions appear instead of returning a 500 status code
			return handler(subpath, request)
		return get_error(404)

	def check_headers(self, request: PreparedRequest):
		"""Check headers, returns None if everything is fine, a Response otherwise."""
		if request.headers.get("Accept", None) != "application/json":
			# According to the documentation the accept header should always be set to json
			return {
				"status_code": 400,
				"reason": "Wrong Accept header",
				"body": "<h1>Accept header is missing or not set to 'application/json'.</h1>",
			}
		if request.headers.get("Authorization", None) != self.auth:
			return get_error(401)
		return None

	def objects(self, subpath, request: PreparedRequest):
		"""Handle /objects/<type>[/<name>] requests."""
		ret = self._objects0(subpath, request)
		return {"status_code": 200, "body": json.dumps(ret)}

	def _objects0(self, subpath, request: PreparedRequest):
		"""Handle /objects/<type>[/<name>] requests, returns the object itself."""
		method = get_method(request)
		otype, name = list_elongation(subpath.split('/'), 2)

		if method == "GET":
			if name:
				return OBJECTS[otype].get(name)
			# TODO Need to parse filters here ............................
			return OBJECTS[otype]

		raise NotImplementedError("Only HTTP GET is implemented yet...")


class StreamableBytesIO(BytesIO):
	"""File-like object that simulates to be an urllib3 response for requests to be streamable."""

	def stream(self, chunk_size, decode_content):
		"""Stream content like requests expects it from an urllib3 response."""
		while self.tell() < len(self.getvalue()):
			data = self.read(chunk_size)
			if data:
				yield data


class IcingaMockAdapter(BaseAdapter):
	"""An adapter to communicate with the mocked Icinga instance."""

	def __init__(self, hosts=("icinga", ), ports=(1234, ), settings_hook=None, **kwargs):
		super().__init__()
		self.hosts = hosts
		self.ports = ports
		# Settings hook that gets called with the settings used for a request
		self.settings_hook = settings_hook or (lambda **_: None)
		self.icinga = Icinga(**kwargs)

	def check_path(self, url):
		"""Return tuple of (path, subpath) for the given URL, raises exception when needed."""
		parsed = urlparse(url)
		if parsed.hostname not in self.hosts:
			raise ConnectionError("Invalid hostname")
		if parsed.port not in self.ports:
			raise ConnectionError("Invalid port")

		return parsed.path

	def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None):
		request.url = request.url.decode("utf-8") if isinstance(request.url, bytes) else request.url
		# Check URL, ask the fake Icinga to handle it
		self.check_path(request.url)
		resp = self.icinga.handle(request)

		# Create response, emulate equests.adapters.HTTPAdapter behavior a bit
		response = Response()
		response.status_code = resp.get("status_code", None)
		response.headers = CaseInsensitiveDict(resp.get("headers", {}))
		response.encoding = get_encoding_from_headers(response.headers)
		response.reason = resp.get("reason", None)
		response.url = request.url  # Already decoded above
		response.request = request
		response.raw = StreamableBytesIO(resp.get("body", "").encode("utf-8"))
		# Cookie jar is not mocked, as Icinga doesn't use cookies
		# response.connection is not mocked, because it's not a response attribute by default

		# Call settings hook with the settings used for this request (to make testing with these easier)
		self.settings_hook(stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies)

		return response

	def close(self):
		"""Close the adapter."""
		pass


def mock_adapter(session: Session, *args, **kwargs):
	"""Add IcingaMockAdapter to the given session, remove all other adapters."""
	# Close adapters for save removal
	session.close()
	session.adapters = OrderedDict()
	adapter = IcingaMockAdapter(*args, **kwargs)
	session.mount("mock://", adapter)
