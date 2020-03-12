# -*- coding: utf-8 -*-
"""
This module provides a mocked "Icinga" to communicate with.

It's quite dirty, but should do its work for the tests...
"""

from collections import OrderedDict
from collections.abc import Sequence
from copy import deepcopy
from io import BytesIO
import json
import os
from urllib.parse import urlparse, unquote_plus

from requests import Session
from requests.adapters import BaseAdapter
from requests.models import PreparedRequest, Response
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from requests.exceptions import ConnectionError

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


def get_parameters(url, body=None):
	"""Get parameters, either from URL query parameters or JSON-encoded body."""
	# Convert URL query parameters to a dict; using parameter keys multiple times is not specified in the Icinga API doc
	ret = dict([unquote_plus(param).split("=", 1) for param in urlparse(url).query.split("&") if "=" in param])
	# Convert body to a dict
	if body:
		if isinstance(body, bytes):
			body = body.decode("utf-8")
		ret.update(json.loads(body))
	return ret


def parse_attrs(attrs):
	"""Parse an attrs sequence/dict to have tuples as keys/items."""
	if isinstance(attrs, Sequence):
		ret = [item.split(".") for item in attrs]
	else:
		ret = dict()
		for key, value in attrs.items():
			ret[tuple(key.split("."))] = value
	return ret


class Icinga:
	"""A fake Icinga "instance" for testing without a real Icinga."""

	ATTRS = ("auth", )

	def __init__(self, **kwargs):
		for attr in self.ATTRS:
			# Get attribute value from kwargs, default to icinga_mock_data defaults
			setattr(self, attr, kwargs.get(attr, DEFAULTS.get(attr)))

		# Get a copy of the objects to work with
		self.object_data = deepcopy(OBJECTS)

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
		if isinstance(ret, int):
			return get_error(ret)
		return {"status_code": 200, "body": json.dumps({"results": ret})}

	def _objects0(self, subpath, request: PreparedRequest):
		"""Handle /objects/<type>[/<name>] requests, returns the object itself."""
		method = get_method(request)
		otype, name = list_elongation(subpath.split('/'), 2)
		parameters = get_parameters(request.url, request.body)

		# Parse attrs
		parameters["attrs"] = parse_attrs(parameters.get("attrs", dict()))
		# Translate <otype>.attr to attrs.attr
		d = dict(parameters["attrs"])
		for key, value in d.items():
			if f"{key[0]}s" == otype.lower():
				del parameters["attrs"][key]
				parameters["attrs"][key[1:]] = value

		if method == "PUT":
			# Create object with parameters["attrs"] dict
			if not name:
				return 404
			self.object_data[otype][name] = dict()
			self.object_data[otype][name]["attrs"] = parameters["attrs"]
			return [{"code": 200, "status": "Object was created."}]

		# Filter
		objects = list()
		if name:
			try:
				objects.append(self.object_data[otype][name])
			except KeyError:
				return 404
		else:
			objects = list(self.object_data[otype].values())
		# TODO Parse other filters than name...

		if method == "GET":
			return objects
		if method == "POST":
			res = list()
			# Modify objects according to parameters["attrs"] dict
			for obj in objects:
				obj = obj["attrs"]
				for key, value in parameters["attrs"].items():
					o = obj
					# Special case for vars, because they can be None
					if key[0] == "vars" and o["vars"] is None:
						o["vars"] = dict()

					for attr in key[:-1]:
						o = o[attr]
					o[key[-1]] = value
					res.append({"code": 200, "name": obj["name"], "status": "Attributes updated", "type": otype})
			return res

		raise NotImplementedError(f"Method {method} is not implemented")

	def types(self, subpath, request: PreparedRequest):
		"""Handle /types request."""
		method = get_method(request)
		if method != "GET":
			return 404

		with open(os.path.join(os.path.dirname(__file__), "icinga_types.json"), 'r') as file:
			data = json.load(file)

		if not subpath:
			# Return all
			return {"status_code": 200, "body": json.dumps(data)}

		# Return one object
		for i, obj in enumerate(data["results"]):
			if obj["name"] == subpath:
				return {"status_code": 200, "body": {"results": json.dumps(data["results"][i])}}

		return get_error(404)

	def events(self, subpath, request: PreparedRequest):
		"""Simulate event streams (without streaming)."""
		# POST request to /v1/events and nothing else
		if get_method(request) != "POST":
			return get_error(404)
		if subpath and subpath[0] != "?":
			return get_error(400)

		parameters = get_parameters(request.url, request.body)
		# Check that this is set
		_ = parameters["queue"]
		# Set type, as the real Icinga does
		parameters["type"] = parameters["types"][0]
		# Return lines with the parameters dict multiple times...
		parameters = json.dumps(parameters)
		return {"status_code": 200, "body": "\n".join((parameters for _ in range(9)))}


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


def mock_session(session: Session, *args, **kwargs):
	"""Add IcingaMockAdapter to the given session, remove all other adapters."""
	# Close adapters for save removal
	session.close()
	# Remove all adapters
	session.adapters = OrderedDict()
	# Add mock adapter
	adapter = IcingaMockAdapter(*args, **kwargs)
	# HTTP because requests.PreparedRequest.prepare_url() handles only URLs starting with "http"
	session.mount("http://", adapter)


def mock_session_handler(session: Session, *args, **kwargs):
	"""Add IcingaMockAdapter to the given session, remove all other adapters, close session after tests."""
	mock_session(session, *args, **kwargs)
	# With to make sure the session is closed after the tests
	with session:
		yield session
