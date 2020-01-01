# -*- coding: utf-8 -*-
"""Small client for easy access to the Icinga2 API. Famous Python package requests is needed as a dependency.
(https://github.com/requests/requests)

This client is really dump and has not much ideas about how the Icinga2 API works.
What it does is to set up a requests.Session (which it extends), build URL and body, and construct request and response
at the end. By default the constructed request is a models.APIRequest, and the constructed response a
models.APIResponse. It's possible to override these defaults in a subclass.
"""

import requests

from .models import APIRequest, APIResponse

# Accepted HTTP methods
HTTP_METHODS = {'GET', 'POST', 'PUT', 'DELETE'}

# Default request class
DEFAULT_REQUEST_CLASS = APIRequest
# Default response class
DEFAULT_RESPONSE_CLASS = APIResponse


class API(requests.Session):
	"""API session for easily sending requests and getting responses.

	Objects of this class are used for constructing a request, that than will use it's `prepare_request` and
	`create_response` methods for sending the request and constructing the response.
	The preparation method is inherited from the requests.Session superclass.
	"""

	def __init__(self, url, **sessionparams):
		"""Construct the API session with an URL and "optional" further parameters (like authentication, ...)."""
		super().__init__()
		self.base_url = url

		# Set session parameters like verify, proxies, auth, ...
		for key, value in sessionparams.items():
			setattr(self, key, value)

	@property
	def request_class(self):
		"""The class used as a request - this is done to simplify extending the API class changing it's behavior."""
		return DEFAULT_REQUEST_CLASS

	def create_response(self, response):
		"""Create a custom response from a requests.Response."""
		return DEFAULT_RESPONSE_CLASS(response)

	@classmethod
	def from_pieces(cls, host, port=5665, url_prefix='/v1', **sessionparams):
		"""Simplified creation of an API object."""
		url = "https://{}:{}{}/".format(host, port, url_prefix)
		return cls(url, **sessionparams)

	@classmethod
	def clone(cls, obj):
		"""Clone the object."""
		sessionparams = {}
		for attr in obj.__attrs__:
			sessionparams[attr] = getattr(obj, attr, None)
		api = cls(obj.base_url, **sessionparams)
		return api

	def __getattr__(self, item):
		"""Return a RequestBuilder object with the given first item."""
		return self.s(item)

	def s(self, item):
		"""Return a RequestBuilder object with the given first item."""
		return self.RequestBuilder(self).s(item)

	def __truediv__(self, item):
		"""Return a RequestBuilder object with the given first item."""
		return self.RequestBuilder(self).s(item)

	class RequestBuilder:
		"""Class to build a request and it's dictionary (JSON) body."""

		def __init__(self, api):
			"""Initiate a RequestBuilder with an API object (needed for some attributes and to pass it to the request."""
			self.api_client = api
			self._lastattr = None  # last attribute -> call to put in body, or not to add it to the URL
			self._builder_list = []  # URL Builder, joined with "/" at the and
			self._body = {}  # Request body as dictionary

		def _rotate_attr(self, new=None):
			"""Helper method, as this functionality is needed twice.

			The "last used attr" is rotated. If nothing was done with the last used attr yet, it's added to the URL
			builder list. A new last used attr is set if given.
			"""
			if self._lastattr is not None:
				self._builder_list.append(self._lastattr)
				self._lastattr = None
			if new is not None:
				self._lastattr = new
			return self

		def __getattr__(self, item):
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			return self.s(item)

		def __truediv__(self, item):
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			return self.s(item)

		def s(self, item):
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			if item.upper() not in HTTP_METHODS:
				return self._rotate_attr(item)

			# item was a accepted HTTP method -> construct a request
			self._rotate_attr()
			# Construct URL with base url from api client + the "/"-joined builder list
			url = self.api_client.base_url + "/".join(self._builder_list)
			return self.api_client.request_class(self.api_client, item.upper(), url, json=self._body)

		def __call__(self, *args, **kwargs):
			"""Call last item means to not put it into URL builder list but into the body."""
			# First argument if one, otherwise add the whole list of arguments to the body
			args = args[0] if len(args) == 1 else args
			if self._lastattr in self._body and isinstance(self._body[self._lastattr], list):
				# Add args to existing list
				self._body[self._lastattr] += args
			elif args is not None:
				# Set body field to args
				self._body[self._lastattr] = args
			# Reset last used attr
			self._lastattr = None
			return self
