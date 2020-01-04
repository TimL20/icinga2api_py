# -*- coding: utf-8 -*-
"""This module contains classes essential for sending requests and receiving responses.

A long time ago, the classes of this module were the `api` module. The classes are used in that essential module as
requests and responses to/from the Icinga2 API.
"""

import logging
import collections.abc
from requests import Request, Response
from . import exceptions

LOGGER = logging.getLogger(__name__)


class APIRequest(Request):
	"""Apecialised requests that may be sent to the Icinga2 API.

	Mainly, objects of this cladd have the following features:
	- method_override property for the 'X-HTTP-Method-Override' header field, while the HTTP method is set to POST
		unless explicitely changed.
	- On prepare(), the APIRequest is prepared using an API object (which is a requests.Session)
	- The APIRequest gets prepared and sent when the object gets called (which will also return an appropriate response
		of course).
	"""

	attrs = ("method", "url", "headers", "files", "data", "params", "auth", "cookies", "hooks", "json")

	def __init__(self, api, *args, **kwargs):
		"""Initiate an APIRequest with an API object.

		:param api: API object, used to prepare the request (using the requests Session feature)
		:param *args: Get passed to the super constructor
		:param **kwargs: Get passed to the super constructor
		"""
		super().__init__(*args, **kwargs)

		# Client is supposed to be a api.API instance, which inherits from requests.Session
		self.api = api

		# To keep it simple everything is handled with method-override, and the standard method is post
		if self.method is not None:
			self.method_override = self.method
		self.method = "POST"
		# Set accept header to JSON, as it's standard.
		self.headers['Accept'] = "application/json"

	@property
	def method_override(self):
		"""The X-HTTP-Method_Override header field value."""
		return self.headers.get("X-HTTP-Method-Override")

	@method_override.setter
	def method_override(self, method):
		"""The X-HTTP-Method_Override header field value."""
		self.headers['X-HTTP-Method-Override'] = method.upper()

	def clone(self):
		"""Clone this APIRequest."""
		request = self.__class__(self.api)
		for attr in self.attrs:
			val = getattr(self, attr)
			# Copy Mappings (e.g. headers)
			val = dict(val) if isinstance(val, collections.abc.Mapping) else val
			setattr(request, attr, val)
		return request

	def __eq__(self, other):
		"""True if all attributes of these two APIRequests are the same."""
		return all((getattr(self, attr, None) == getattr(other, attr, None) for attr in self.attrs))

	def prepare(self):
		"""Construct a requests.PreparedRequest with the API (client) session."""
		return self.api.prepare_request(self)

	def send(self, params):
		"""Send this request.

		The request gets prepared before sending. Given keyword arguments are merged into the URL parameters.
		The returned response is created via create_response() of the API object.
		:param params: Parameters to merge into the URL parameters.
		:return: A response created by create_response() of the API object.
		"""
		# Update URL parameters (optional)
		self.params.update(params)
		LOGGER.debug("API %s request to %s with %s", self.method_override, self.url, self.json)
		# Get a prepared request
		request = self.prepare()
		# Take environment variables into account
		settings = self.api.merge_environment_settings(request.url, None, None, None, None)
		r = self.api.send(request, **settings)
		return self.api.create_response(r)

	def __call__(self, *args, **params):
		"""Send this request, see send()."""
		return self.send(params)


class Query(APIRequest):
	"""A query that has the ability to do different things for different requests."""

	def request(self, params=None):
		"""Get an APIRequest equivalent to this Query."""
		request = APIRequest(self.api)
		for attr in APIRequest.attrs:
			val = getattr(self, attr)
			# Copy Mappings (e.g. headers)
			val = dict(val) if isinstance(val, collections.abc.Mapping) else val
			setattr(request, attr, val)
		# Update GET parameters
		if params:
			request.params.update(params)
		return request

	def __call__(self, *args, **kwargs):
		"""Let a handler return the "handled" request."""
		return self.handler()(self.request(kwargs))

	def handler(self):
		"""Get a callable to give the request to."""
		return self.handle_request

	@staticmethod
	def handle_request(request):
		"""Default handler: send the request, returns a response from api.create_response()."""
		return request.send()


class APIResponse(Response):
	"""Represents a response from the Icinga2 API."""

	def __init__(self, response):
		super().__init__()
		# TODO find out if there is a better way than just copy every important attribute
		self.__setstate__(response.__getstate__())

	def __eq__(self, other):
		try:
			return self.__getstate__() == other.__getstate__()
		except AttributeError:
			return NotImplemented

	def json(self, **kwargs):
		"""JSON encoded content of the response (if any). Returns None on error."""
		try:
			return super().json(**kwargs)
		except ValueError:
			# No valid JSON encoding
			return None

	def results(self, **kwargs):
		"""Return a sequence for the results (values of "results" in the response data parsed as JSON)."""
		try:
			data = self.json(**kwargs)
		except TypeError:
			raise exceptions.InvalidIcinga2ApiResponseError()
		else:
			try:
				return tuple(data["results"])
			except KeyError:
				return tuple()

	def __str__(self):
		"""Simple string representation."""
		status = "{} ({})".format(self.status_code, self.reason) if self.reason else self.status_code
		return "<{} {} from {}>".format(self.__class__.__name__, status, self.url)
