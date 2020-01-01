# -*- coding: utf-8 -*-
"""This module contains some different useful client classes for getting in touch with the Icinga2 API."""

import json

from .api import API
from .models import Query, APIResponse, APIRequest
from .results import ResultsFromResponse, CachedResultSet, Result
from .base_objects import Icinga2Objects, Icinga2Object
from . import objects


class Client(API):
	"""Standard Icinga2 API client for non-streaming content."""

	def __init__(self, url, results_class=None, **sessionparams):
		super().__init__(url, **sessionparams)
		self.results_class = results_class or ResultsFromResponse

	def create_response(self, response):
		"""Return appropriate ResultSet object.."""
		return self.results_class(response=APIResponse(response))


class StreamClient(API):
	"""Icinga2 API client for streamed content."""

	def __init__(self, url, **sessionparams):
		sessionparams["stream"] = True
		super().__init__(url, **sessionparams)

	def create_response(self, response):
		"""Create a stream of Result objects.

		APIResponse doesn't work here, because it uses __getstate__, which waits until the whole content is consumed
		- something that propably does never happen in this case.
		"""
		return self.ResultsStream(response)

	class ResultsStream:
		"""Return Result objects for streamed lines."""

		def __init__(self, response):
			self._response = response

		def __iter__(self):
			"""Yield Result objects for every line received."""
			for line in self._response.iter_lines():
				if line:
					res = json.loads(line)
					yield Result((res, ))

		def close(self):
			"""Close stream connection."""
			self._response.close()

		def __enter__(self):
			"""Usage as an context manager closes the stream connection automatically on exit."""
			return self

		def __exit__(self, exc_type, exc_val, exc_tb):
			"""Usage as an context manager closes the stream connection automatically on exit."""
			self.close()


class Icinga2(API):
	"""An object oriented Icinga2 API client."""

	def __init__(self, url, cache_time=float("inf"), **sessionparams):
		super().__init__(url, **sessionparams)
		self.cache_time = cache_time

	@property
	def request_class(self):
		return Query

	def client(self):
		"""Get standard client."""
		return Client.clone(self)

	def api(self):
		"""Get basic API client."""
		return API.clone(self)

	@staticmethod
	def results_from_query(request):
		"""Returns a ResultsFromResponse from the given request."""
		# Transformation to APIRequest is done by API.create_response (inherited)
		return ResultsFromResponse(response=request())

	def object_from_query(self, type_, request, name=None, **kwargs):
		"""Get a appropriate python object to represent whatever is requested with the request.
		This method assumes, that a named object is singular (= one object). The name is not used.
		Remaining kwargs are passed to the constructor (Icinga2Object, Host, ...)."""
		type_ = type_[:-1] if name is not None and type_[-1] == "s" else type_
		class_ = getattr(objects, type_.title(), None)
		initargs = {"cache_time": self.cache_time}
		if name is not None:
			initargs["name"] = name
		initargs.update(kwargs)
		if class_ is not None:
			return class_(request=request, **initargs)
		if name is not None:
			# it's one object if it has a name
			return Icinga2Object(request=request, **initargs)
		return Icinga2Objects(request=request, **initargs)

	def cached_results_from_query(self, request, **kwargs):
		"""Get a CachedResultSet with the given request. Remaining kwargs are passed to the constructor."""
		initargs = {"cache_time": self.cache_time}
		initargs.update(kwargs)
		return CachedResultSet(request=request, **initargs)

	def create_object(self, type_, name, attrs, templates=tuple(), ignore_on_error=False):
		"""Create an Icinga2 object through the API."""
		type_ = type_.lower()
		type_ = type_ if type_[-1:] == "s" else type_ + "s"
		return self.client().objects.s(type_).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error)).put()  # Fire request immediately
