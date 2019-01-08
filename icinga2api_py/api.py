# -*- coding: utf-8 -*-
"""Small client for easy access to the Icinga2 API. Famous python package requests is needed as a dependency.

This client is really dump and has not much ideas about how the Icinga2 API works.
What it does is to set up a requests.Session (which it extends), build URL and body, and make the request in the end.
By default the response is a requests.Response.
"""
import logging
import requests

# Accepted HTTP methods
HTTP_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


class API(requests.Session):
	"""This class is not documented, because the examples show much better how it works than everything else could."""
	def __init__(self, host, auth=None, port=5665, uri_prefix='/v1', response_parser=None, **sessionparams):
		super().__init__()
		self.base_url = "https://{}:{}{}/".format(host, port, uri_prefix)

		# Set session parameters like verify, proxies, ...
		for key, value in sessionparams.items():
			setattr(self, key, value)

		# Shortcut, because this auth method is often used, and programmers are lazy
		if auth is not None:
			self.auth = auth

		self.response_parser = response_parser

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
			return self.api_client.Request(self.api_client, url, self._body, item.upper())

		def __call__(self, *args, **kwargs):
			args = args[0] if len(args) == 1 else args
			if self._lastattr in self._body and isinstance(self._body[self._lastattr], list):
				self._body[self._lastattr] += args
			elif args is not None:
				self._body[self._lastattr] = args
			self._lastattr = None
			return self

	class Request:
		def __init__(self, client, url, body, method):
			self.api = client

			# Prepare request
			headers = {'Accept': 'application/json', 'X-HTTP-Method-Override': method.upper()}
			self.request = requests.Request('POST', url, headers=headers, json=body)

		def __call__(self, *args, **params):
			self.request.params = params or {}
			logging.getLogger(__name__).debug("API request to %s with %s", self.request.url, self.request.json)
			request = self.api.prepare_request(self.request)
			# Take environment variables into account
			settings = self.api.merge_environment_settings(request.url, None, None, None, None)
			r = self.api.send(request, **settings)
			return r if not self.api.response_parser else self.api.response_parser(r)
