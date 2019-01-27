# -*- coding: utf-8 -*-
"""Small client for easy access to the Icinga2 API. Famous Python package requests is needed as a dependency.

This client is really dump and has not much ideas about how the Icinga2 API works.
What it does is to set up a requests.Session (which it extends), build URL and body, and make the request in the end.
By default the response is a models.APIResponse.
"""

import requests

from .models import APIRequest, APIResponse

# Accepted HTTP methods
HTTP_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


class API(requests.Session):
	"""This class is not documented, because the examples show much better how it works than everything else could."""
	def __init__(self, host, auth=None, port=5665, uri_prefix='/v1', **sessionparams):
		super().__init__()
		self.base_url = "https://{}:{}{}/".format(host, port, uri_prefix)

		# Set session parameters like verify, proxies, ...
		for key, value in sessionparams.items():
			setattr(self, key, value)

		# Shortcut, because this auth method is often used, and programmers are lazy
		if auth is not None:
			self.auth = auth

		# This is here to simplify extending the API class and changing its behavior
		self.request_class = APIRequest

	def clone(self):
		sessionparams = {}
		for attr in self.__attrs__:
			sessionparams[attr] = getattr(self, attr, None)
		api = API(None, **sessionparams)
		api.base_url = self.base_url
		api.request_class = self.request_class
		return api

	def __getattr__(self, item):
		return self.s(item)

	def s(self, item):
		return self.RequestBuilder(self).s(item)

	class RequestBuilder:
		def __init__(self, api):
			self.api_client = api
			self._lastattr = None  # last attribute -> call to put in body, or not to add it to the URL
			self._builder_list = []  # URL Builder
			self._body = {}  # Request body as dictionary

		def _rotate_attr(self, new=None):
			if self._lastattr is not None:
				self._builder_list.append(self._lastattr)
				self._lastattr = None
			if new is not None:
				self._lastattr = new
			return self

		def __getattr__(self, item):
			return self.s(item)

		def s(self, item):
			if item.upper() not in HTTP_METHODS:
				return self._rotate_attr(item)
			self._rotate_attr()
			url = self.api_client.base_url + "/".join(self._builder_list)
			return self.api_client.request_class(self.api_client, item.upper(), url, json=self._body)

		def __call__(self, *args, **kwargs):
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
