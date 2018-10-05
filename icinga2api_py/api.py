# -*- coding: utf-8 -*-
"""Small client for easy access to the Icinga2 API. Famous python package requests is needed as a dependency.

This client is really dump and has not much ideas about how the Icinga2 API works.
All responses are directly from a requests.post() call, from here you have to process them by yourself.
Nothing here is thread-safe, create shallow copies for usage in different threads.

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
	"""This class is not documented, because the examples show much better how it works than everything else could."""
	def __init__(self, host, auth=tuple(), cert_auth=tuple(), port=5665, uri_prefix='/v1', verify=False, response_parser=None):
		self.verify = verify
		self.auth = auth  # Basic auth tuple (username, password)
		self.cert = cert_auth  # Client side authentication (certificate, key) tuple
		self.response_parser = response_parser

		self.base_url = "https://{}:{}{}/".format(host, port, uri_prefix)
		self._reset()

	def _reset(self):
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
		if item.upper() in HTTP_METHODS:
			self._rotate_attr()
			ret = self.Request(self, self.base_url + "/".join(self._builder_list), self._body, item.upper())
			self._reset()
			return ret
		return self._rotate_attr(item)

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
			self.client = client
			self.url = url
			self.body = body  # HTTP body as dictionary.
			self.method = method  # HTTP method to set X-HTTP-Method-Override later
			self.request_args = {"verify": self.client.verify}
			if self.client.cert:
				self.request_args["cert"] = self.client.cert
			else:
				self.request_args["auth"] = self.client.auth
			# TODO look at requests.Session and requests.Request, could that make an improvement?

		def __call__(self, *args, **params):
			data = json.dumps(self.body)
			headers = {'Accept': 'application/json', 'X-HTTP-Method-Override': self.method.upper()}
			kwargs = {"data": data, "params": params, "headers": headers}
			kwargs.update(self.request_args)  # To make overriding easy, especially for child classes
			logging.getLogger(__name__).debug("API request to %s with %s", self.url, kwargs["data"])
			r = requests.post(self.url, **kwargs)
			return r if self.client.response_parser is None else self.client.response_parser(r)
