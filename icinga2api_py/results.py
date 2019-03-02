# -*- coding: utf-8 -*-
"""
This module contains all relevant stuff regarding the results attribute of an Icinga2 API response.
Very similar to the module models.
"""

import collections.abc
import time


class ResultSet(collections.abc.Sequence):
	"""Represents a set of results returned from the Icinga2 API."""
	def __init__(self, results=None):
		"""Construct a ResultSet with an APIResponse."""
		self._results = results

	def load(self):
		"""Load results into _results. It's here to be overridden."""
		pass

	@property
	def results(self):
		"""All results as a ("naked") sequnce. Meant for internal use."""
		if self._results is None:
			self.load()
		return self._results

	@property
	def loaded(self):
		"""True if results are loaded."""
		return self._results is not None

	def result(self, index):
		"""Return result at the given index, or a ResultSet."""
		if isinstance(index, slice):
			return ResultSet(self.results[index])
		return Result(self.results[index])

	def __getitem__(self, index):
		"""Return one result at given index, or a ResultSet."""
		return self.result(index)

	def __len__(self):
		"""Length of the result sequence."""
		return len(self.results)

	def __bool__(self):
		"""Return True if results are loaded and there are results."""
		return self.loaded and bool(self.results)

	def __str__(self):
		"""Return short string representation."""
		res = "?" if not self.loaded else "no" if not len(self) else len(self)
		return "<{} with {} results>".format(self.__class__.__name__, res)

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
				except (KeyError, TypeError):
					# KeyError if no such key, TypeError if r is not a dict
					if raise_nokey:
						raise KeyError("No such key")
					else:
						r = nokey_value
						break
			ret.append(r)
		return ret

	def where(self, attr, expected):
		"""Return list of results with expected value as attribute."""
		attr = Result.parseAttrs(attr)
		ret = []
		for res in self.results:
			r = res
			for key in attr:
				try:
					r = r[key]
				except (KeyError, TypeError):
					r = KeyError
					break
			if r == expected:
				ret.append(res)
		return ResultSet(ret)

	def count(self, attr, expected):
		"""Return number of attributes having an expected value."""
		attr = Result.parseAttrs(attr)
		cnt = 0
		for r in self.results:
			for key in attr:
				try:
					r = r[key]
				except (KeyError, TypeError):
					r = KeyError
					break
			if r == expected:
				cnt += 1
		return cnt

	def are_all(self, attr, expected):
		"""Return True if all attributes have an expected value."""
		attr = Result.parseAttrs(attr)
		keyerror = expected == KeyError
		for r in self.results:
			for key in attr:
				try:
					r = r[key]
				except (KeyError, TypeError):
					if not keyerror:
						return False
			if r != expected and not keyerror:
				return False
		return True

	def min_one(self, attr, expected):
		"""Return True if minimum one attribute has an expected value"""
		attr = Result.parseAttrs(attr)
		keyerror_expected = expected == KeyError
		for r in self.results:
			for key in attr:
				try:
					r = r[key]
				except (KeyError, TypeError):
					if keyerror_expected:
						return True
			if r == expected:
				return True
		return False

	def min_max(self, attr, expected, min, max):
		"""Return True if minimum *min* and maximum *max* results attributes have an expected value."""
		attr = Result.parseAttrs(attr)
		i = 0
		for r in self.results:
			for key in attr:
				try:
					r = r[key]
				except (KeyError, TypeError):
					r = KeyError
					break
			if r == expected:
				i += 1
				if i > max:
					return False
		return i >= min


class ResultsFromResponse(ResultSet):
	"""ResultSet from a given APIResponse."""
	def __init__(self, response):
		super().__init__()
		self._response = response

	@property
	def response(self):
		"""The original response from the Icinga2 API."""
		return self._response

	def load(self):
		"""Parse results of response."""
		self._results = self.response.results()

	def __str__(self):
		"""Return short string representation."""
		res = "?" if not self.loaded else "no" if not len(self) else len(self)
		return "<{} with {} results, status {}>".format(self.__class__.__name__, res, self.response.status_code)


class ResultsFromRequest(ResultSet):
	"""ResultSet loaded (once) on demand from a given request."""
	def __init__(self, request):
		super().__init__()
		self._request = request
		self._response = None
		self._results = None

	@property
	def response(self):
		"""Loads response with use of the request. This property is ironically called from the load method."""
		if self._response is None:
			self._response = self._request()
		return self._response

	def load(self):
		"""Parse results of response. Calls the response property to load the response from the request."""
		self._results = self.response.results()

	@property
	def loaded(self):
		"""True if a successful load has taken place."""
		return self._response is not None and self._results is not None

	def __str__(self):
		"""Return short string representation."""
		res = "?" if not self.loaded else "no" if not len(self) else len(self)
		return "<{} with {} results, status {}>".format(self.__class__.__name__, res, self.response.status_code)


class CachedResultSet(ResultsFromRequest):
	"""ResultSet from a request with caching."""
	def __init__(self, request, cache_time, response=None, results=None):
		"""ResultSet from Request with caching.
		:param request The request returning the represented results
		:param cache_time Cache expiry time in seconds
		:param response APIResponse for this request if already loaded.
		:param results Optional results as list if already loaded."""
		super().__init__(request)
		self._response = response
		self._results = results
		self._expiry = cache_time
		self._expires = cache_time
		self._hold = None

	@property
	def response(self):
		"""The original response from the Icinga2 API. Reloads on cache expiry."""
		if self._expires < time.time():
			self._response = None
		return super().response

	def load(self):
		"""Reset cache expiry time and (re-)load response."""
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
		"""True if a successful load has taken place and cache is not expired."""
		return super().loaded and self._expires >= time.time()

	@property
	def cache_time(self):
		return self._expiry

	@cache_time.setter
	def cache_time(self, cache_time):
		if self.held:
			self._hold = cache_time
		else:
			self._expiry = cache_time

	def invalidate(self):
		"""Reset propably cached things."""
		self._response = None
		self._results = None

	def hold(self):
		"""Set cache expiry to infinite to suppress reload by cache expiry.
		Call unhold() to undo this, the old cache expiry value is stored."""
		if self.held:
			raise ValueError("Cannot hold twice.")

		self._hold = self._expires
		self._expires = float("inf")

	def drop(self):
		"""Undo hold - cache expiry is set to old value."""
		if self._hold is None:
			raise ValueError("Cannot drop without hold.")

		self._expires = self._hold
		self._hold = None

	@property
	def held(self):
		"""Whether or not hold() was called without drop()."""
		return self._hold is None

	def __enter__(self):
		self.hold()

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.drop()


class ResultList(ResultSet, collections.abc.MutableSequence):
	"""Mutable results representation, with all nice features of ResultSet."""
	def __delitem__(self, index):
		del self.results[index]

	def __setitem__(self, index, value):
		self.results[index] = value

	def insert(self, index, value):
		self.results.insert(index, value)


class Result(ResultSet, collections.abc.Mapping):
	"""Icinga2 API request result (one from results).
	This class appears as a sequence with length one, also if more than one result is stored in the background.
	The inheritance from Mapping does not make a difference for that, it's just to simplify attribute access (which is
	the whole purpose of this class)."""
	def __init__(self, results=None):
		# Transform results into a tuple if it's not a Sequence (or None)
		results = results if isinstance(results, collections.abc.Sequence) or results is None else (results,)
		super().__init__(results)

	def result(self, index=0):
		return self

	@staticmethod
	def parseAttrs(attrs):
		"""Split attrs on dots, return attrs if it's not a string."""
		if isinstance(attrs, str):
			return attrs.split(".")
		else:
			return attrs

	def __getitem__(self, item):
		"""Implements Mapping and sequence access in one."""
		if isinstance(item, int) or isinstance(item, slice):
			return self.result(item)

		# Mapping access
		try:
			ret = self._results[0]
			for item in self.parseAttrs(item):
				ret = ret[item]
			return ret
		except (KeyError, ValueError):
			raise KeyError("No such key: {}".format(item))

	def __len__(self):
		"""Length of this sequence - this is always 1."""
		return 1

	def __iter__(self):
		"""Iterate of the "sequence" item (this one and only object).
		This is not useful for this class, but to avoid trouble caused by the inheritance structure."""
		yield self
