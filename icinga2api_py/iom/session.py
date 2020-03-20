# -*- coding: utf-8 -*-
"""This module puts all Icinga-object-mapping things together.
"""

import functools
import logging

from ..api import API
from ..clients import Client
from ..models import Query
from ..results import CachedResultSet
from .base import TypeNumber, ParentObjectDescription
from . import Types

LOGGER = logging.getLogger(__name__)


class Session(API):
	"""The client for getting mapped Icinga objects."""
	def __init__(self, url, cache_time=float("inf"), **sessionparams):
		super().__init__(url, **sessionparams)
		self.cache_time = cache_time
		self.types = Types(self)

	@property
	def request_class(self):
		return IOMQuery

	def client(self):
		"""Get non-OOP interface client. This is done by calling clone() of Client."""
		return Client.clone(self)

	def api(self):
		"""Get most simple client (API)."""
		return API.clone(self)


class IOMQuery(Query):
	"""Query to return an appropriate object for a request on a session."""

	# Identifiers that identify configuration objects
	OBJECT_IDENTIFIERS = {"object", "objects"}

	def handler(self):
		"""Decide what to do, when the query gets executed, return a callable to handle the request."""
		# Immediatelly send if the HTTP method is not GET and not overriden with GET
		if self.method != "GET" and self.method_override != "GET":
			return self.handle_request

		# Cut base url
		url = self.url[self.url.find(self.api.base_url) + len(self.api.base_url):]
		# Split by /
		url = "" if not url else url.split("/")
		basetype = url[0]
		# Return as CachedResultSet
		# TODO this doesn't handle special cases handled by simple_oo.OOQuery (e.g. console)
		if basetype not in self.OBJECT_IDENTIFIERS:
			return lambda request: CachedResultSet(request=request)

		# A configuration object was queried
		return functools.partial(self.create_object, url)

	def create_object(self, url_split, request):
		"""Create configuration object with the given request."""
		otype = url_split[1]
		if len(url_split) > 2:
			# Has a name, so it's one object
			class_ = self.api.types.type(otype, TypeNumber.SINGULAR)
		else:
			class_ = self.api.types.type(otype, TypeNumber.PLURAL)
		LOGGER.debug("Using class %s for URL %s", class_.__name__, url_split)
		# Now create the object, parent_descr has the session this object belongs to
		parent_descr = ParentObjectDescription(session=self.api)
		return class_(request=request, parent_descr=parent_descr)
