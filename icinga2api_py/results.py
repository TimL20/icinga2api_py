# -*- coding: utf-8 -*-
"""This module contains all relevant stuff regarding the results attribute of an Icinga2 API response."""

import collections.abc
import time
from . import exceptions


class ResultSet(collections.abc.Sequence):
	"""Represents a set of results returned from the Icinga2 API."""
	def __init__(self, response):
		"""Construct a ResultSet with an APIResponse."""
		self._response = response
		self._results = None

	@property
	def response(self):
		"""Return the original response."""
		return self._response

	def load(self):
		"""Parse results of response."""
		try:
			data = self.response.json()
			self._results = tuple(data["results"])
		except (KeyError, TypeError):
			# No results in body or wrong type
			self._results = None  # TODO evaluate that line
			raise exceptions.InvalidIcinga2ApiResponseError()

	@property
	def results(self):
		"""Returns loaded results, loads them if needed."""
		if self._results is None:
			self.load()
		return self._results

	@property
	def loaded(self):
		"""True if results are loaded."""
		return self._results is not None

	def result(self, index):
		"""Return result at the given index."""
		return Result(self.results[index])

	def __getitem__(self, index):
		"""Return one result at given index."""
		return self.result(index)

	def __len__(self):
		"""Length of the result sequence."""
		return len(self.results)

	def __bool__(self):
		"""Return True if results are loaded and there are results."""
		return self.loaded and bool(self.results)

	def __str__(self):
		"""Return short string representation."""
		res = "no" if not bool(self) else len(self)
		return "<ResultSet with {} results, status {}>".format(res, self.response.status_code)

	###################################################################################################################
	# Enhanced access to result data ##################################################################################
	###################################################################################################################

	def values(self, attr, raise_nokey=False, nokey_value=None):
		"""Return all values of the given attribute as list.
		:param attr Attribute (usually as a string)
		:param raise_nokey True to immediately reraise catched KeyError
		:param nokey_value Value to put in for absent keys (if KeyErrors are not raised)."""
		attr = Result.parseAttrs(attr)
		ret = []
		for r in self.results:
			for key in attr:
				try:
					r = r[key]
				except KeyError:
					# TODO check if that TypeError thing occurs again here...
					if raise_nokey:
						raise
					else:
						r = nokey_value
						break
			ret.append(r)
		return ret

	def are_all(self, attr, expected):
		"""Return True if all attributes have an expected value."""
		attr = Result.parseAttrs(attr)
		for r in self.results:
			for key in attr:
				r = r[key]
			if r != expected:
				return False
		return True

	def min_one(self, attr, expected):
		"""Return True if minimum one attribute has an expected value"""
		attr = Result.parseAttrs(attr)
		for r in self.results:
			for key in attr:
				r = r[key]
			if r == expected:
				return True
		return False

	def min_max(self, attr, expected, min, max):
		"""Return True if minimum *min* and maximum *max* results attributes have an expected value."""
		# TODO care about KeyErrors
		attr = Result.parseAttrs(attr)
		i = 0
		for r in self.results:
			for key in attr:
				r = r[key]
			if r == expected:
				i += 1
				if i > max:
					return False
		return i >= min


class ResultsFromRequestMixin:
	"""ResultSet mixin implementing load (once) on demand."""
	def __init__(self, request):
		"""ResultSet from Request constructor."""
		self._request = request
		self._response = None
		self._results = None

	@property
	def response(self):
		"""Loads response with use of the request. This property is ironically called from the load method."""
		if self._response is None:
			self._response = self._request()
		return self._response

	@property
	def loaded(self):
		return self._response is not None and self._results is not None


class CachedResultSet(ResultsFromRequestMixin, ResultSet):
	"""ResultSet mixin implementing caching."""
	def __init__(self, request, caching, response=None):
		"""ResultSet from Request with caching.
		:param request The request returning the represented results
		:param caching Cache expiry time in seconds
		:param response APIResponse for this request if already loaded."""
		super().__init__(request)
		self._response = response
		self._expiry = caching
		self._expires = caching

	@property
	def response(self):
		if self._expires < time.time():
			self._response = None
		return super().response

	def load(self):
		"""Reset cache expiry and (re-)load response."""
		self._expires = time.time() + self._expiry
		super().load()

	@property
	def results(self):
		"""Extends results access with timed caching."""
		if self._expires < time.time():
			self._results = None
		return super().results

	@property
	def loaded(self):
		return super().loaded and self.expires >= time.time()

	def invalidate(self):
		"""Point out, that the cached response is propably not valid anymore."""
		self._response = None
		self._results = None


class Result(collections.abc.Mapping):
	"""Icinga2 API request result (one from results).
	Basically just provides (read-only) access to the data of a dictionary."""
	def __init__(self, res):
		self._data = res

	@staticmethod
	def parseAttrs(attrs):
		"""Split attrs on dots, return attrs if it's not a string."""
		if isinstance(attrs, str):
			return attrs.split(".")
		else:
			return attrs

	def __getitem__(self, item):
		ret = self._data
		for item in self.parseAttrs(item):
			ret = ret[item]
		return ret

	def __getattr__(self, item):
		return self[item]

	def __len__(self):
		return len(self._data)

	def __iter__(self):
		return iter(self._data)

	def __str__(self):
		return str(self._data)
