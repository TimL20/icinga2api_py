# -*- coding: utf-8 -*-
"""This module contains classes essential for sending requests and receiving responses.

A long time ago, the classes of this module were the `api` module. The classes are used in that essential module as
requests and responses to/from the Icinga2 API.
"""

import logging
import collections.abc
from requests import Request, Response
from . import exceptions


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
		logging.getLogger(__name__).debug("API %s request to %s with %s", self.method_override, self.url, self.json)
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
	"""Helper class to return an appropriate object for a query.

	This class is part of the object oriented layer of the API (client "Icinga"). It suffers from bad design and will
	hopefully improve somewhen in the future, or may be removed.
	"""

	# Information where to find the object type and name for which URL schema
	# If None, than the result is supposed to be a results.ResultsFromResponse
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
		"""Get a object representing the result of this query."""
		# Get request for this query
		request = self.request()
		# Cut base url
		url = self.url[self.url.find(self.api.base_url)+len(self.api.base_url):]
		# Split by /
		url = "" if not url else url.split("/")
		basetype = url[0]
		if basetype in self.TYPES_AND_NAMES:
			if self.TYPES_AND_NAMES[basetype] is None:
				# Not an object, so don't return an object
				return self.api.results_from_query(request)  # Fire APIRequest

			# Information about type and name in URL is known
			type_ = url[self.TYPES_AND_NAMES[basetype][0]]
			namepos = self.TYPES_AND_NAMES[basetype][1]
			name = url[namepos] if len(url) > namepos > 0 else None
		else:
			# Default type guessing, should work
			type_ = basetype
			name = None
		# Cut last letter 's' of plural form if name is known (= if single object)
		type_ = type_[:-1] if name is not None and type_[-1:] == "s" else type_
		# Append letter 's' if it's not a single object (= name not known) - only to avoid confusion...
		type_ = type_ + 's' if name is None and type_[-1] != "s" else type_
		logging.getLogger(__name__).debug("Assumed type %s and name %s from URL %s", type_, name, self.url)

		if "name" in kwargs:
			name = kwargs["name"]
			del kwargs["name"]

		# Distinct between objects and results
		if basetype == "objects":
			return self.api.object_from_query(type_, request, name, **kwargs)
		else:
			return self.api.cached_results_from_query(request, **kwargs)


class APIResponse(Response):
	"""Represents a response from the Icinga2 API."""

	def __init__(self, response):
		super().__init__()
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
