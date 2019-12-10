# -*- coding: utf-8 -*-
"""This module will contain almost all of the different Icinga2 API clients."""

import json
from .api import API
from .models import Query, APIResponse, APIRequest
from .results import ResultsFromResponse, CachedResultSet, Result
from .base_objects import Icinga2Objects, Icinga2Object
from . import objects


class Client(API):
	"""Icinga2 API client for non-streaming content, without objects."""
	def __init__(self, url, **sessionparams):
		super().__init__(url, **sessionparams)

	@staticmethod
	def create_response(response):
		"""Return ResultSet with APIResponse with given response."""
		return ResultsFromResponse(response=APIResponse(response))


class StreamClient(API):
	"""Icinga2 API client for streamed content."""
	def __init__(self, url, **sessionparams):
		sessionparams["stream"] = True
		super().__init__(url, **sessionparams)

	@staticmethod
	def create_response(response):
		"""APIResponse doesn't work here, because it uses __getstate__, which waits until the whole content is consumed
		- something that propably does never happen in this case."""
		return StreamClient.ResponseStream(response)

	class ResponseStream:
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
	"""A client for the object oriented part."""
	def __init__(self, url, cache_time=float("inf"), **sessionparams):
		super().__init__(url, **sessionparams)
		self.cache_time = cache_time
		self.request_class = Query

	def client(self):
		"""Get non-OOP interface client."""
		client = Client.clone(self)
		client.create_response = Client.create_response
		client.request_class = APIRequest
		return client

	def api(self):
		"""Get basic API client."""
		api = API.clone(self)
		api.create_response = API.create_response
		api.request_class = APIRequest
		return api

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
			return class_(request, **initargs)
		if name is not None:
			# it's one object if it has a name
			return Icinga2Object(reqeust=request)
		return Icinga2Objects(reqeust=request)

	def cached_results_from_query(self, request, **kwargs):
		"""Get a CachedResultSet with the given request. Remaining kwargs are passed to the constructor."""
		initargs = {"cache_time": self.cache_time}
		initargs.update(kwargs)
		return CachedResultSet(request=request)  # TODO how to solve that???

	def create_object(self, type_, name, attrs, templates=tuple(), ignore_on_error=False):
		"""Create an Icinga2 object through the API."""
		type_ = type_.lower()
		type_ = type_ if type_[-1:] == "s" else type_ + "s"
		return self.client().objects.s(type_).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error)).put()  # Fire request immediately
