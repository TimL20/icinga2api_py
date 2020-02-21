# -*- coding: utf-8 -*-
"""This module contains client classes for getting in touch with the Icinga2 API, but only of the layer 2 of this
library. See the docs for more information."""

import json

from .api import API
from .models import Query
from .results import ResultsFromResponse, Result


class ClientQuery(Query):
	"""A flexible query, trying to return everything as the results_class of the Client object."""

	def handle_request(self, request):
		"""Handle the request by passing it to the Client's results_class if possible, pass the response otherwise."""
		try:
			# Try to pass the request
			return self.api.results_class(request=request, **self.api.results_parameters)
		except TypeError:
			# Failed to pass the request, pass the response
			# The request.send() method will use API.create_response(), which returns a APIResponse
			return self.api.results_class(response=request.send(), **self.api.results_parameters)


class Client(API):
	"""Standard Icinga2 API client for non-streaming content."""

	def __init__(self, url, results_class=None, results_parameters=None, **sessionparams):
		"""The client takes, compared two the simpler API client, two additional parameters for customization.

		:param url: The base URL as for :class:`API`
		:param results_class: The class (or any other callable) to create the results with. The given class or callable
			get passed an :class:`icinga2api_py.models.APIRequest` as a "request" parameter value. If that fails with a
			TypeError (which it	does if there is no "request" keyword argument), a
			:class:`icinga2api_py.models.APIResponse` is passed as a "response" parameter value (that is required to s
			ucceed).
			This scenario is designed this way to support both :class:`icinga2api_py.results.ResultsFromRequest` and
			:class:`icinga2api_py.results.ResultsFromResponse` based classes.
		:param results_init_parameters: Keyword arguments (as a dict) that are additionally passed to the
			``results_class``
		:param sessionparams: Session parameters as for :class:`API`
		"""
		super().__init__(url, **sessionparams)
		self.results_parameters = results_parameters or dict()
		self.results_class = results_class or ResultsFromResponse

	@property
	def request_class(self):
		return ClientQuery


class StreamClient(API):
	"""Icinga2 API client for streamed content."""

	def __init__(self, url, **sessionparams):
		sessionparams["stream"] = True
		super().__init__(url, **sessionparams)

	def create_response(self, response):
		"""Create a stream of Result objects.

		The streamed events have a format that differ from any other Icinga2 API response (JSON objects on lines
		instead of on object containing results). Also this can't be implemented as a sized container of results, and
		the connection is not closed automatically after results are consumed (as new results are streamed).
		That why this is a class very different from the other results classes.
		"""
		return self.ResultsStream(response)

	class ResultsStream:
		"""Return Result objects for streamed lines."""

		#: Response attributes, properties and methods that are made available in :meth:`__getattr__`
		response_attrs = {
			"status_code", "headers", "url", "history", "reason", "cookies", "elapsed", "request",
			"__bool__", "__nonzero__",
			"ok", "is_redirect", "is_permanent_redirect", "next", "links", "raise_for_status",
		}

		def __init__(self, response):
			self._response = response

		def __getattr__(self, item):
			"""Some response attributes are made available here."""
			if item in self.response_attrs:
				return getattr(self._response, item)

			raise AttributeError(f"No such attribute: {item}")

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
