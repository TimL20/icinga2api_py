# -*- coding: utf-8 -*-
"""In this module are objects important for functionality."""

import logging
from requests import Request, Response


class APIRequest(Request):
	"""A ready-to-call API request specialised for the Icinga2 API."""
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
