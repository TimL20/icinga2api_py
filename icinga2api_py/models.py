# -*- coding: utf-8 -*-
"""In this module are objects important for functionality."""

import logging
from requests import Request, Response


class APIRequest(Request):
	"""A ready-to-call API request specialised for the Icinga2 API."""
	attrs = ("method", "url", "headers", "files", "data", "params", "auth", "cookies", "hooks", "json")

	def __init__(self, client, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# Client is supposed to be a api.API instance, which inherits from requests.Session
		self.api = client

		# To keep it simple everything is handled with method-override, and the standard method is post
		self.method_override = self.method
		self.method = "POST"
		# Set accept header to JSON
		self.headers['Accept'] = "application/json"

	@property
	def method_override(self):
		try:
			return self.headers['X-HTTP-Method-Override']
		except KeyError:
			return None

	@method_override.setter
	def method_override(self, method):
		self.headers['X-HTTP-Method-Override'] = method.upper()

	def clone(self):
		"""Clone this APIRequest."""
		args = [getattr(self, attr, None) for attr in self.attrs]
		return APIRequest(self.api, *args)

	def prepare(self):
		"""Construct a requests.PreparedRequest with the API (client) session."""
		return self.api.prepare_request(self)

	def __call__(self, *args, **params):
		self.params.update(params)  # Update URL parameters optionally
		logging.getLogger(__name__).debug("API %s request to %s with %s", self.method_override, self.url, self.json)
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
		"templates": (0, 2),  # /templates/<temptype>/<name> -> type=template
		"variables": (0, 1),  # /variables/<name>
		"actions": None,  # not an object
	}

	def clone(self):
		"""Clone this Query."""
		args = [getattr(self, attr, None) for attr in self.attrs]
		return Query(self.api, *args)

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
				request = super().clone()
				return request()  # Fire APIRequest

			# Information about type and name in URL is known
			type_ = url[self.TYPES_AND_NAMES[basetype][0]]
			namepos = self.TYPES_AND_NAMES[basetype][1]
			name = url[namepos] if len(url) > namepos > 0 else None
		else:
			# Default type guessing, usually works
			type_ = basetype
			name = None
		# Cut last letter of plural form if name is known (= if single object)
		type_ = type_[:-1] if name is not None and type_[-1:] == "s" else type_
		logging.getLogger(__name__).debug("Assumed type %s and name %s from URL %s", type_, name, self.url)

		if "name" in kwargs:
			name = kwargs["name"]
			del kwargs["name"]

		# Get a request object by calling clone of super()
		request = super().clone()
		return self.api.object_from_query(type_, request, name, **kwargs)


class APIResponse(Response):
	"""Represents a response from the Icinga2 API."""
	def __init__(self):
		super().__init__()

	@staticmethod
	def from_response(response):
		"""Create a response from a response and return it."""
		res = APIResponse()
		res.__setstate__(response.__getstate__)
		return res

	def json(self, **kwargs):
		"""JSON encoded content of the response (if any). Returns None on error."""
		try:
			return super().json(**kwargs)
		except ValueError:
			# No valid JSON encoding
			return None