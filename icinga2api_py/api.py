# -*- coding: utf-8 -*-
"""Small client for easy access to the Icinga2 API.
It has exactly one dependency: requests

This client is really dump and has not much ideas about how the Icinga2 API works.
All responses are directly from a requests.post() call, from here you have to process them by yourself.

Usage:
Some usage examples
```
from icinga2api_py.api import API
client = API("localhost", ("user", "pass"))
icinga_pid = client.status.IcingaApplication.get().json()["results"][0]["status"]["icingaapplication"]["app"]["pid"]

response = client.objects.services.joins(["host.state"]).attrs(["name", "state"]).filter("host.name==\"localhost\"").get()
# that line does exactly the same as the following line:
response = client.objects.services.attrs("name", "state").filter("host.name==\"localhost\"").joins(["host.state"]).get()

client.actions.s("reschedule-check").filter("service.name==\"ping4\" && host.name==\"localhost\"").type("Service").post()
# that line does exactly the same as the following ugly line:
client.actions.s("reschedule-check").s("filter")("service.name==\"ping4\" && host.name==\"localhost\"").s("type")("Service").s("post")()
```
"""
import json
import logging
import requests

# Accepted HTTP methods
HTTP_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


class API:
	def __init__(self, host, auth, port=5665, uri_prefix='/v1', verify=False, response_parser=None):
		self.verify = verify
		self.auth = auth
		self.response_parser = response_parser

		self._base_url = "https://{}:{}{}/".format(host, port, uri_prefix)

	def __getattr__(self, item):
		return self.s(item)

	def s(self, item):
		return self._RequestBuilder(self, self._base_url, [item])

	class _RequestBuilder:
		def __init__(self, client, base_url, builder_list):
			self.client = client
			self._base_url = base_url  # Base URL (host, port, ...)
			self._lastattr = None  # last attribute -> call to put in body, or not to add it to the URL
			self._builder_list = builder_list  # URL Builder
			self._body = {}

		def _attr(self, new=None):
			if self._lastattr is not None:
				self._builder_list.append(self._lastattr)
				self._lastattr = None
			if new is not None:
				self._lastattr = new
			return self

		def __getattr__(self, item):
			return self.s(item)

		def s(self, string):
			if string.upper() in HTTP_METHODS:
				self._attr()
				return self.client.Request(self.client, self._base_url+"/".join(self._builder_list), self._body, string.upper())
			return self._attr(string)

		def __call__(self, *args, **kwargs):
			args = args[0] if len(args) == 1 else list(args)
			if self._lastattr in self._body:
				if isinstance(self._body[self._lastattr], list):
					self._body[self._lastattr] += args
				elif args:
					self._body[self._lastattr] = args
			elif args:
				self._body[self._lastattr] = args
			self._lastattr = None
			return self

	class Request:
		def __init__(self, client, url, body, method):
			self.client = client
			self.url = url
			self.body = body
			self.method = method

		def __call__(self, *args, **kwargs):
			data = json.dumps(self.body)
			logging.getLogger(__name__).debug("API request to %s with %s", self.url, data)
			# Method override as default
			headers = {'Accept': 'application/json', 'X-HTTP-Method-Override': self.method.upper()}
			r = requests.post(self.url, data=data, params=kwargs,
								headers=headers, auth=self.client.auth, verify=self.client.verify)
			return r if self.client.response_parser is None else self.client.response_parser(r)
