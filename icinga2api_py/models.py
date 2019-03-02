# -*- coding: utf-8 -*-
"""This module provides objects important for functionality."""

import logging
import collections.abc
from requests import Request, Response
from . import exceptions


class APIRequest(Request):
	"""A ready-to-call API request specialised for the Icinga2 API."""
	attrs = ("method", "url", "headers", "files", "data", "params", "auth", "cookies", "hooks", "json")

	def __init__(self, api, *args, **kwargs):
		"""Initiate a APIRequest with an API object. *args and **kwargs are passed to request.Request's init."""
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
		try:
			return self.headers['X-HTTP-Method-Override']
		except KeyError:
			return None

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

	def prepare(self):
		"""Construct a requests.PreparedRequest with the API (client) session."""
		return self.api.prepare_request(self)

	def __call__(self, *args, **params):
		"""Call the request object to prepare and immediately send this request.
		keyword arguments do update params of request. The request is send with use of the API (session) object."""
		self.params.update(params)  # Update URL parameters optionally
		logging.getLogger(__name__).debug("API %s request to %s with %s", self.method_override, self.url, self.json)
		# Prepare the request
		request = self.prepare()
		# Take environment variables into account
		settings = self.api.merge_environment_settings(request.url, None, None, None, None)
		r = self.api.send(request, **settings)
		return self.api.create_response(r)


class Query(APIRequest):
	"""Helper class to return an appropriate object for a query."""

	# Information where to find the object type and name for which URL schema
	TYPES_AND_NAMES = {
		"objects": (1, 2),  # /objects/<type>/<name>
		"templates": (0, 2),  # /templates/<temptype>/<name> -> type=template(s)
		"variables": (0, 1),  # /variables/<name>
		"status": (0, 1),  # /status/<statustype>
		"types": (0, 1),  # /types/<type>
		"actions": None,  # not an object
		"console": None,  # not an object
		"config": None,  # not really objects...
	}

	def request(self):
		"""Get an APIRequest equivalent to this Query."""
		request = APIRequest(self.api)
		for attr in APIRequest.attrs:
			val = getattr(self, attr)
			# Copy Mappings (e.g. headers)
			val = dict(val) if isinstance(val, collections.abc.Mapping) else val
			setattr(request, attr, val)
		return request

	def __call__(self, *args, **kwargs):
		# Find object type and maybe name in URL
		# Cut base url
		url = self.url[self.url.find(self.api.base_url)+len(self.api.base_url):]
		# Split by /
		url = "" if not url else url.split("/")
		basetype = url[0]
		if basetype in self.TYPES_AND_NAMES:
			if self.TYPES_AND_NAMES[basetype] is None:
				# Not an object, so don't return an object
				request = self.request()
				return self.api.results_from_query(request)  # Fire APIRequest

			# Information about type and name in URL is known
			type_ = url[self.TYPES_AND_NAMES[basetype][0]]
			namepos = self.TYPES_AND_NAMES[basetype][1]
			name = url[namepos] if len(url) > namepos > 0 else None
		else:
			# Default type guessing, should work
			type_ = basetype
			name = None
		# Cut last letter of plural form if name is known (= if single object)
		type_ = type_[:-1] if name is not None and type_[-1:] == "s" else type_
		# Append letter 's' if it's not a single object (= name not known) - only to avoid confusion...
		type_ = type_ + 's' if name is None and type_[-1] != "s" else type_
		logging.getLogger(__name__).debug("Assumed type %s and name %s from URL %s", type_, name, self.url)

		if "name" in kwargs:
			name = kwargs["name"]
			del kwargs["name"]

		# Get a request object
		request = self.request()
		return self.api.object_from_query(type_, request, name, **kwargs)


class APIResponse(Response):
	"""Represents a response from the Icinga2 API."""
	def __init__(self, response):
		super().__init__()
		self.__setstate__(response.__getstate__())

	def json(self, **kwargs):
		"""JSON encoded content of the response (if any). Returns None on error."""
		try:
			return super().json(**kwargs)
		except ValueError:
			# No valid JSON encoding
			return None

	def results(self, **kwargs):
		try:
			data = self.json(**kwargs)
			return tuple(data["results"])
		except KeyError:
			return tuple()
		except TypeError:
			raise exceptions.InvalidIcinga2ApiResponseError()
