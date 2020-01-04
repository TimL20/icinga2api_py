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
			return self.api.results_class(request=request)
		except TypeError:
			# Failed to pass the request, pass the response
			# The request.send() method will use API.create_response(), which returns a APIResponse
			return self.api.results_class(response=request.send())


class Client(API):
	"""Standard Icinga2 API client for non-streaming content."""

	def __init__(self, url, results_class=None, **sessionparams):
		super().__init__(url, **sessionparams)
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
