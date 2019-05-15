# -*- coding: utf-8 -*-
"""This module puts all Icinga-object-mapping things together.
"""

from ..api import API
from ..clients import Client
from ..models import Query
from . import Types


class Session(API):
	"""The client for getting mapped Icinga objects."""
	def __init__(self, url, cache_time=float("inf"), **sessionparams):
		super().__init__(url, **sessionparams)
		self.cache_time = cache_time
		self.types = Types(self)

	def client(self):
		"""Get non-OOP interface client. This is done by calling clone() of Client."""
		return Client.clone(self)

	def api(self):
		"""Get most simple client (API)."""
		return API.clone(self)


class IOMQuery(Query):
	"""Helper class to return a appropriate object for a request on a session."""
	OBJECT_IDENTIFIERS = {"object", "objects"}

	def __call__(self, *args, **kwargs):
		"""Get a object for the result of this query, if the type is an object and the HTTP method is GET."""
		# Cut base url
		url = self.url[self.url.find(self.api.base_url) + len(self.api.base_url):]
		# Split by /
		url = "" if not url else url.split("/")
		basetype = url[0]
		if basetype not in self.OBJECT_IDENTIFIERS:
			super().__call__(*args, **kwargs)

		# Get request for this query
		request = self.request()
		if self.method_override == "GET":
			otype = url[1]
			# name = url[2]if len(url) > 2 else None
			class_ = self.api.types.type(otype)
			return class_(self.api, request)

		if self.method_override in {"POST", "DELETE"}:
			# Directly fire request for modification queries
			return request()
