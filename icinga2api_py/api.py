# -*- coding: utf-8 -*-
"""Small client for easy access to the Icinga2 API. Famous Python package requests is needed as a dependency.
(https://github.com/requests/requests)

This client is really dump and has not much ideas about how the Icinga2 API works.
What it does is to set up a requests.Session (which it extends), build URL and body, and construct request and response
at the end. By default the constructed request is a models.APIRequest, and the constructed response a models.APIResponse.
It's possible to override these defaults in a subclass.
"""

import requests

from .models import APIRequest, APIResponse

# Accepted HTTP methods
HTTP_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


class API(requests.Session):
	"""Objects of this class are used to construct a request (and later response). Also this class is a requests.Session
	subclass and therefore also offer that functionality."""
	def __init__(self, url, **sessionparams):
		super().__init__()
		self.base_url = url

		# Set session parameters like verify, proxies, ...
		for key, value in sessionparams.items():
			setattr(self, key, value)

		# This is here to simplify extending the API class and changing its behavior
		self.request_class = APIRequest

	@classmethod
	def from_pieces(cls, host, port=5665, url_prefix='/v1', **sessionparams):
		url = "https://{}:{}{}/".format(host, port, url_prefix)
		return cls(url, **sessionparams)

	@classmethod
	def clone(cls, obj):
		sessionparams = {}
		for attr in obj.__atrrs__:
			sessionparams[attr] = getattr(obj, attr, None)
		api = cls(obj.base_url, **sessionparams)
		api.request_class = obj.request_class
		return api

	def __getattr__(self, item):
		"""Return a RequestBuilder object with the given first item."""
		return self.s(item)

	def s(self, item):
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
			"""Helper method, as this functionality is needed twice."""
			if self._lastattr is not None:
				self._builder_list.append(self._lastattr)
				self._lastattr = None
			if new is not None:
				self._lastattr = new
			return self

		def __getattr__(self, item):
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			return self.s(item)

		def s(self, item):
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			if item.upper() not in HTTP_METHODS:
				return self._rotate_attr(item)
			# item was a accepted HTTP method -> construct a request
			self._rotate_attr()
			url = self.api_client.base_url + "/".join(self._builder_list)
			return self.api_client.request_class(self.api_client, item.upper(), url, json=self._body)

		def __call__(self, *args, **kwargs):
			"""Call last item means to not put it into URL builder list but into the body."""
			args = args[0] if len(args) == 1 else args
			if self._lastattr in self._body and isinstance(self._body[self._lastattr], list):
				self._body[self._lastattr] += args
			elif args is not None:
				self._body[self._lastattr] = args
			self._lastattr = None
			return self

	@staticmethod
	def create_response(response):
		"""Create a custom response from a requests.Response."""
		return APIResponse.from_response(response)
