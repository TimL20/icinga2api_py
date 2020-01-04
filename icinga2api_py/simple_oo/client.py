# -*- coding: utf-8 -*-
"""This module contains query and client of the OO-layer."""

import logging
import functools

from ..api import API
from ..simple_oo.base_objects import Icinga2Objects, Icinga2Object
from ..clients import Client
from ..models import Query
from ..results import ResultsFromResponse, CachedResultSet
from ..simple_oo import objects

LOGGER = logging.getLogger(__name__)


class OOQuery(Query):
	"""Helper class to return an appropriate object for a query.

	This class is part of the object oriented layer of the API (client "Icinga"). It suffers from bad design and will
	hopefully improve somewhen in the future, or may be removed.
	"""

	# Information where to find the object type and name for which URL schema
	# If None, than the result is supposed to be a results.ResultsFromResponse
	TYPES_AND_NAMES = {
		"objects": (1, 2),  # /objects/<type>/<name>
		"templates": (0, 2),  # /templates/<temptype>/<name> -> type=template(s)
		"variables": (0, 1),  # /variables/<name>
		"status": (0, 1),  # /status/<statustype>
		"types": (0, 1),  # /types/<type>
		"actions": None,  # not an object
		"console": None,  # not an object
		"config": None,  # not really objects...
	}

	def _url_infos(self):
		"""Read basetype, type and name from the URL if possible (returns a tuple with these three things, everything
		could be None)."""
		# Cut base url
		url = self.url[self.url.find(self.api.base_url) + len(self.api.base_url):]
		# Split by /
		url = "" if not url else url.split("/")
		basetype = url[0]

		if basetype in self.TYPES_AND_NAMES:
			if self.TYPES_AND_NAMES[basetype] is None:
				return basetype, None, None

			# Information about type and name in URL is known
			type_ = url[self.TYPES_AND_NAMES[basetype][0]]
			namepos = self.TYPES_AND_NAMES[basetype][1]
			name = url[namepos] if len(url) > namepos > 0 else None
		else:
			# Default type guessing, should work
			type_ = basetype
			name = None

		# Cut last letter 's' of plural form if name is known (= if single object)
		type_ = type_[:-1] if name is not None and type_[-1:] == "s" else type_
		# Append letter 's' if it's not a single object (= name not known)
		type_ = type_ + 's' if name is None and type_[-1] != "s" else type_
		LOGGER.debug("Assumed type %s and name %s from URL %s", type_, name, self.url)
		return basetype, type_, name

	def handler(self):
		"""Decide what to do when this query object gets called, return a callable that handles the request."""
		# Immediatelly send if the HTTP method is not GET and not overriden with GET
		if self.method != "GET" and self.method_override != "GET":
			return self.handle_request

		basetype, type_, name = self._url_infos()
		if basetype in self.TYPES_AND_NAMES:
			if self.TYPES_AND_NAMES[basetype] is None:
				# Transform to a ResultsFromResponse object
				return self.results_from_query

		# Distinct between objects and simple results
		if basetype == "objects":
			return functools.partial(self.object_from_query, type_, name)
		else:
			return self.cached_results_from_query

	@staticmethod
	def results_from_query(request):
		"""Returns a ResultsFromResponse from the given request."""
		# Transformation to APIRequest is done by API.create_response (inherited)
		return ResultsFromResponse(response=request())

	@staticmethod
	def cached_results_from_query(request):
		"""Get a CachedResultSet with the given request."""
		return CachedResultSet(request=request)

	def object_from_query(self, type_, name, request):
		"""Get a appropriate Python object to represent whatever is requested with this query.

		This method assumes, that a named object is singular (= one object). The name is not used.
		"""
		# Look for a class specialised for that object type in the objects module
		class_ = getattr(objects, type_.title(), None)
		if class_ is not None:
			# Found a class, so return an appropriate object of that class
			return class_(request=request, cache_time=self.api.cache_time)
		if name is not None:
			# It's one object if it has a name
			return Icinga2Object(request=request, cache_time=self.api.cache_time)
		return Icinga2Objects(request=request, cache_time=self.api.cache_time)


class Icinga2(API):
	"""An object oriented Icinga2 API client."""

	def __init__(self, url, cache_time=float("inf"), **sessionparams):
		super().__init__(url, **sessionparams)
		self.cache_time = cache_time

	@property
	def request_class(self):
		return OOQuery

	def client(self):
		"""Get standard client."""
		return Client.clone(self)

	def api(self):
		"""Get basic API client."""
		return API.clone(self)

	def create_object(self, type_, name, attrs, templates=tuple(), ignore_on_error=False):
		"""Create an Icinga2 object through the API."""
		type_ = type_.lower()
		type_ = type_ if type_[-1:] == "s" else type_ + "s"
		return self.client().objects.s(type_).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error)).put()  # Fire request immediately
