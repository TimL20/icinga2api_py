# -*- coding: utf-8 -*-
"""This module puts all Icinga-object-mapping things together.
"""

import logging

from ..api import API
from ..clients import Client
from ..models import APIRequest, Query
from .base import Number
from . import Types

LOGGER = logging.getLogger(__name__)


class Session(API):
	"""The client for getting mapped Icinga objects."""
	def __init__(self, url, cache_time=float("inf"), **sessionparams):
		super().__init__(url, **sessionparams)
		self.request_class = IOMQuery
		self.cache_time = cache_time
		self.types = Types(self)

	def client(self):
		"""Get non-OOP interface client. This is done by calling clone() of Client."""
		return Client.clone(self)

	def api(self):
		"""Get most simple client (API)."""
		api = API.clone(self)
		# TODO any way to set the default, whatever that is?
		api.request_class = APIRequest
		return api


class IOMQuery(Query):
	"""Helper class to return an appropriate object for a request on a session."""
	OBJECT_IDENTIFIERS = {"object", "objects"}

	def __call__(self, *args, **kwargs):
		"""Get an object for the result of this query, if the type is an object and the HTTP method is GET."""
		# Cut base url
		url = self.url[self.url.find(self.api.base_url) + len(self.api.base_url):]
		# Split by /
		url = "" if not url else url.split("/")
		basetype = url[0]
		if basetype not in self.OBJECT_IDENTIFIERS:
			LOGGER.debug("No object identifier recognized in %s for URL %s", self.__class__.__name__, url)
			return super().__call__(*args, **kwargs)

		# Get request for this query
		request = self.request()
		if self.method_override == "GET":
			otype = url[1]
			# TODO add name+SINGULAR case
			# name = url[2]if len(url) > 2 else None
			class_ = self.api.types.type(otype, Number.PLURAL)
			LOGGER.debug("Using class %s for URL %s (%s)", class_.__name__, url, self.__class__.__name__)
			return class_(self.api, request)

		if self.method_override in {"POST", "DELETE"}:
			# Directly fire request for modification queries
			return request()
