# -*- coding: utf-8 -*-
"""This module contains classes essential for sending requests and receiving responses.

A long time ago, the classes of this module were the `api` module. The classes are used in that essential module as
requests and responses to/from the Icinga2 API.
"""

import logging
import collections.abc
import warnings

from requests import Request, Response

from . import exceptions

LOGGER = logging.getLogger(__name__)


class APIRequest(Request):
	"""Specialised request with all data that may be sent in a ``requests.PreparedRequest`` to the Icinga2 API.

	Mainly, objects of this class have the following features:

	- method_override property for the 'X-HTTP-Method-Override' header field, while the HTTP method is set to POST \
		unless explicitely changed.
	- On prepare(), the APIRequest is prepared using an API object (which is a ``requests.Session``)
	- The APIRequest gets prepared and sent when the object gets called (which will also return an appropriate \
		response of course).
	"""

	#: All request attributes any object of this class has
	attrs = ("method", "url", "headers", "params", "auth", "cookies", "hooks", "json")

	def __init__(self, api, method=None, url=None, json=None, headers=None, auth=None, cookies=None, hooks=None):
		"""Initiation requires an API client instance, the other init parameters are passed on to ``requests.Request``.

		:param api: API object, used to prepare the request (using the requests Session feature)
		:param method: Request method to override with
		:param url: Full request URL
		:param json: Body to JSON-encode
		:param headers: Request headers
		:param auth: auth handler or (user, pass) tuple
		:param cookies: dictionary or CookieJar to attach to the request
		:param hooks: dictionary of callback hooks
		"""

		super().__init__(
			# Statically set method to post, adding method_override below
			method="POST",
			url=url,
			# Pass the json body, it's used as long as files and data are empty
			json=json,
			# Just pass on the rest
			headers=headers,
			auth=auth,
			cookies=cookies,
			hooks=hooks
		)

		#: The API client is supposed to be a api.API instance, which inherits from requests.Session
		self.api = api

		# To keep it simple everything is handled with method-override, and the standard method is post
		if method is not None:
			self.method_override = method

	@property
	def data(self):
		"""Always return empty data to avoid weird behavior."""
		return []

	@data.setter
	def data(self, data):
		"""Do nothing because only a json body is used for an APIRequest.

		It still is implemented to be compatible with the :class:`requests.Request` parent class.
		"""
		if data:
			warnings.warn(f"{self.__class__.__name__} object ignores when 'data' is set", Warning)

	@property
	def files(self):
		"""Always return no files to avoid weird behavior."""
		return []

	@files.setter
	def files(self, files):
		"""Do nothing because only a json body is used for an APIRequest.

		It still is implemented to be compatible with the :class:`requests.Request` parent class.
		"""
		if files:
			warnings.warn(f"{self.__class__.__name__} object ignores when 'files' is set", Warning)

	@property
	def method_override(self):
		"""The X-HTTP-Method_Override header field value."""
		return self.headers.get("X-HTTP-Method-Override")

	@method_override.setter
	def method_override(self, method):
		"""The X-HTTP-Method_Override header field value."""
		self.headers['X-HTTP-Method-Override'] = method.upper()

	def clone(self) -> "APIRequest":
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

	def send(self, params=None):
		"""Send this request.

		The request gets prepared before sending.
		The returned response is created via create_response() of the API object.

		:param params: Parameters (as a mapping) to merge into the URL parameters.
		:return: A response created by create_response() of the API object.
		"""
		if params:
			# Update URL parameters (optional)
			self.params.update(params)
		LOGGER.debug("API %s request to %s with %s", self.method_override, self.url, self.json or self.data)
		# Get a prepared request
		request = self.prepare()
		# Take environment variables into account (especially for proxies...)
		settings = self.api.merge_environment_settings(request.url, {}, None, None, None)
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


class APIResponse:
	"""Represents a response from the Icinga2 API.

	This is basically just a wrapper for ``requests.Response``, adding only minor features.
	"""

	def __init__(self, response: Response):
		#: The :class:`requests.Response` this APIRequest wraps
		self.response = response

	def __getattr__(self, item):
		"""Get an attribute of the response."""
		return getattr(self.response, item)

	def __eq__(self, other):
		"""Check whether this response has the same url, status_code, reason, headers and content as other."""
		try:
			# Attributes and properties to compare
			attrs = ("url", "status_code", "reason", "headers", "content")
			for attr in attrs:
				if getattr(self, attr) != getattr(other, attr):
					return False
		except AttributeError:
			return NotImplemented
		else:
			return True

	def json(self, **kwargs):
		"""JSON encoded content of the response (if any). Returns None on error."""
		try:
			return self.response.json(**kwargs)
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
		status = f"{self.status_code} ({self.reason})" if self.reason else self.status_code
		return f"<{self.__class__.__name__} {status} for {self.url}>"
