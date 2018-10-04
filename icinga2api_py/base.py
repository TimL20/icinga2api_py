# -*- coding: utf-8 -*-
"""This module contains the representations of Icinga2 objects and other classes, that are important for
this high-level API client.
"""

from .api import API

import json
import collections.abc


class Icinga2ApiError(Exception):
	"""Indication, that something went wrong when communicating with the Icinga2 API."""
	pass


class Client(API):
	"""Icinga2 API client."""
	def __init__(self, host, auth, port=5665, uri_prefix='/v1', cert=False):
		super().__init__(host, auth, port, uri_prefix, cert)

	class Request(API.Request):
		def __call__(self, *args, **kwargs):
			return Response(super().__call__(*args, **kwargs))


class Result(collections.abc.Mapping):
	"""Icinga2 API request result (one from results).
	Basically just provides access to the data of a dictionary."""
	def __init__(self, res):
		self._data = res

	def __getitem__(self, item):
		return self._data.__getitem__(item)

	def __len__(self):
		return self._data.__len__()

	def __iter__(self):
		return self._data.__iter__()


class Response(collections.abc.Sequence):
	def __init__(self, response):
		self._response = response

		self._results = None
		try:
			self._data = self._response.json()
			self._results = tuple(self._data["results"])
		except json.decoder.JSONDecodeError:
			raise Icinga2ApiError("Failed to parse JSON response.")
		except KeyError:
			pass  # No "results" in _data

	def get(self, item):
		if hasattr(self._data, item):
			return getattr(self._data, item)
		if hasattr(self._response, item):
			return getattr(self._response, item)

	def __getattr__(self, item):
		return self.get(item)

	def __getitem__(self, index):
		return Result(self._results.__getitem__(index))

	def __len__(self):
		return self._results.__len__()

	def __bool__(self):
		return self._results is not None

	###################################################################################################################
	# Enhanced access to result data ##################################################################################
	###################################################################################################################

	def all(self, attr, expected):
		"""Returns True, if all results attributes have the expected value."""
		for r in self._results:
			if r[attr] != expected:
				return False
		return True

	def min_one(self, attr, expected):
		"""Return True, if min. one result attribute has the expected value."""
		# TODO test if set is faster
		for r in self._results:
			if r[attr] == expected:
				return True
		return False

	def min_max(self, attr, expected, min, max):
		"""Returns True, if the result attribute attr has at least min times and maximally max times the expected value"""
		i = 0
		for r in self._results:
			if r[attr] == expected:
				i += 1
				if i > max:
					return False
		return i < min
