# -*- coding: utf-8 -*-
"""
This module contains all relevant stuff regarding the results attribute of an Icinga2 API response.
"""

import collections.abc
import time
import typing


class ResultSet(collections.abc.Sequence):
	"""Represents a set of results returned from the Icinga2 API."""
	def __init__(self, results=None):
		"""Construct a ResultSet with a results sequence or None."""
		self._results = results

	def load(self):
		"""Load results into _results. It's here to be overridden."""
		self._results = tuple()

	@property
	def results(self):
		"""All results as a ("naked") sequence. Meant for internal use."""
		if self._results is None:
			self.load()
		return self._results

	@property
	def loaded(self):
		"""True if results are loaded."""
		return self._results is not None

	def result(self, index):
		"""Return result at the given index, or an appropriate ResultSet for a slice."""
		if isinstance(index, slice):
			return ResultSet(self.results[index])
		return Result(self.results[index])

	def __getitem__(self, index):
		"""Return result at the given index, or an appropriate ResultSet for a slice."""
		return self.result(index)

	def __len__(self):
		"""Length of the results sequence."""
		return len(self.results)

	def __bool__(self):
		"""Return True if results are loaded and there are results."""
		return self.loaded and bool(self.results)

	def __eq__(self, other):
		"""NotImplemented if the other is not a ResultSet; True if all results are equal."""
		if not isinstance(other, ResultSet):
			return NotImplemented
		if len(self) != len(other):
			return False
		for i in range(len(self)):
			if self.results[i] != other.results[i]:
				return False
		return True

	def __str__(self):
		"""Return short string representation."""
		res = "?" if not self.loaded else "no" if not len(self) else len(self)
		return "<{} with {} results>".format(self.__class__.__name__, res)

	###################################################################################################################
	# Enhanced access to result data ##################################################################################
	###################################################################################################################

	@staticmethod
	def parse_attrs(attrs):
		"""Parse attrs string. Split attrs on dots."""
		if not isinstance(attrs, str):
			return attrs

		return attrs.split('.')

	def values(self, attr, raise_nokey=False, nokey_value=None):
		"""Return all values of the given attribute as list.
		:param attr Attribute (usually as a string)
		:param raise_nokey True to immediately reraise catched KeyError
		:param nokey_value Value to put in for absent keys (if KeyErrors are not raised)."""
		attr = self.parse_attrs(attr)
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
		attr = self.parse_attrs(attr)
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

	def number(self, attr, expected):
		"""Return number of attributes having an expected value."""
		attr = self.parse_attrs(attr)
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
		attr = self.parse_attrs(attr)
		for r in self.results:
			for key in attr:
				try:
					r = r[key]
				except (KeyError, TypeError):
					r = KeyError
					break
			if r != expected:
				return False
		return True

	def min_one(self, attr, expected):
		"""Return True if minimum one attribute has an expected value"""
		attr = self.parse_attrs(attr)
		for r in self.results:
			for key in attr:
				try:
					r = r[key]
				except (KeyError, TypeError):
					r = KeyError
					break
			if r == expected:
				return True
		return False

	def min_max(self, attr, expected, min, max):
		"""Return True if minimum *min* and maximum *max* results attributes have an expected value."""
		attr = self.parse_attrs(attr)
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
	def __init__(self, results=None, response=None, json_kwargs=None):
		"""Init ResultsFromResponse object with a response. Optional give kwargs for JSON load."""
		super().__init__(results)
		self._response = response
		self._json_kwargs = json_kwargs or dict()

	@property
	def response(self):
		"""The original response from the Icinga2 API."""
		return self._response

	def load(self):
		"""Parse results of response."""
		try:
			self._results = self.response.results(**self._json_kwargs)
		except AttributeError:
			super().load()

	@property
	def loaded(self):
		"""True if a successful load has taken place."""
		return self._response is not None and self._results is not None

	def __str__(self):
		"""Return short string representation."""
		res = "?" if not self.loaded else "no" if not len(self) else len(self)
		return "<{} with {} results, status {}>".format(self.__class__.__name__, res, self.response.status_code)


class ResultsFromRequest(ResultsFromResponse):
	"""ResultSet loaded (once) on demand from a given request."""
	def __init__(self, results=None, request=None, response=None, json_kwargs=None):
		"""Init ResultsFromRequest object with a request. Optional give kwargs for JSON load."""
		super().__init__(results, response, json_kwargs)
		self._request = request
		self._results = None

	@property
	def request(self):
		"""The request of this ResultsFromRequest object."""
		return self._request

	@property
	def response(self):
		"""Loads response with use of the request. This property is ironically called from the load method."""
		if self._response is None:
			self._response = self._request()
		return self._response

	def __eq__(self, other):
		"""True if other is also a ResultsFromRequest object and they both have the same request, or the superclass's
		__eq__ returns True."""
		if isinstance(other, ResultsFromRequest):
			return self._request == other._request or super().__eq__(other)
		return super().__eq__(other)

	def __str__(self):
		"""Return short string representation."""
		res = "?" if not self.loaded else "no" if not len(self) else len(self)
		return "<{} with {} results, status {}>".format(self.__class__.__name__, res, self.response.status_code)


class CachedResultSet(ResultsFromRequest):
	"""ResultSet from a request with caching. Note that actions like iterating over a CachedResultSet should be aware of
	the fact, that the underlying data can change at any time.
	You can hold to temporarily disable cache reloading and drop to re-enable caching after hold.
	A CachedResultSet also won't reload on cache expiry if used as a context manager (just "with cachedresultset:...")"""
	def __init__(self, results=None, request=None, response=None, json_kwargs=None,
				cache_time=float("inf"), next_cache_expiry=None):
		"""ResultSet from Request with caching.
		:param results Optional results as list if already loaded
		:param request The request returning the represented results
		:param response APIResponse for this request if already loaded
		:param json_kwargs Keyword arguments to pass to the JSON decoder
		:param cache_time Cache expiry time in seconds
		:param next_cache_expiry Set the next cache expiry timestamp, or None
		"""
		super().__init__(results, request, response, json_kwargs)
		self._expiry = cache_time
		self._expires = next_cache_expiry or cache_time
		self._hold = None

	@property
	def response(self):
		"""The original response from the Icinga2 API. Reloads on cache expiry."""
		if self._expires < time.time():
			self._response = None
		return super().response

	def load(self):
		"""Reset cache expiry time and (re-)load response."""
		self._response = None
		super().load()
		self._expires = time.time() + self._expiry

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

	def fixed(self):
		"""Get a ResultSet with the results currently loaded. This is in some situations better than the hold mechanism,
		althought the purpose is very similar."""
		return ResultSet(self.results)

	def hold(self):
		"""Set cache expiry to infinite to suppress reload by cache expiry.
		Call drop() to undo this, the old cache expiry value is stored until drop."""
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
		return self._hold is not None

	def __enter__(self):
		self.hold()

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.drop()


class ResultList(ResultSet, collections.abc.MutableSequence):
	"""Mutable results representation, with all nice features of ResultSet."""
	def __init__(self, results=None):
		super().__init__(None)
		self._results = [] if results is None else list(results)

	def _check_type(self, value):
		"""Raise exception for illegal type."""
		if not isinstance(value, Result):
			raise TypeError("Value in ResultList must be a result.")

	def result(self, index):
		"""Return result at the given index, or a ResultSet."""
		if isinstance(index, slice):
			return ResultList(self.results[index])
		return self.results[index]

	def __delitem__(self, index):
		del self.results[index]

	def __setitem__(self, index, value):
		self._check_type(value)
		self.results[index] = value

	def insert(self, index, value):
		self._check_type(value)
		self.results.insert(index, value)


# Union is not exactly right here, but almost...
SingleResultMixinType = typing.Union["SingleResultMixin", ResultSet]


class SingleResultMixin:
	"""Mixin for ResultSet to represent exactly one instead of any number of results.
	This class appears as a sequence with length one, but also is an immutable Mapping."""

	def __init__(self: SingleResultMixinType, results=None, *args, **kwargs):
		if isinstance(results, collections.abc.Sequence):
			try:
				results = (results[0], )
			except IndexError:
				results = tuple()
		else:
			results = (results, )

		super().__init__(results, *args, **kwargs)

	def result(self: SingleResultMixinType, index):
		"""Get the result - which is always this object itself."""
		if isinstance(index, int) and index >= len(self):
			# It's a sized container...
			raise IndexError
		if isinstance(index, slice):
			# Make sure that only one object is returned by slicing a made-up example tuple
			example = (True,).__getitem__(index)
			return [self] if any(example) else list()

		return self

	@property
	def _raw(self: SingleResultMixinType):
		"""Get the "raw" result as a dictionary. Meant for internal use only."""
		return self.results[0]

	def __getitem__(self: SingleResultMixinType, item):
		"""Implements Mapping and sequence access in one."""
		if isinstance(item, int) or isinstance(item, slice):
			return self.result(item)

		# Mapping access
		try:
			ret = self._raw
			for item in self.parse_attrs(item):
				ret = ret[item]
			return ret
		except (KeyError, ValueError):
			raise KeyError("No such key: {}".format(item))

	def __contains__(self: SingleResultMixinType, item):
		"""Whether there is a value for the given key, or the value is in the results list."""
		try:
			self[item]
		except (KeyError, IndexError):
			pass
		else:
			return True

		return item == self

	def keys(self: SingleResultMixinType):
		"""A set-like object providing a view on the Results keys."""
		return collections.abc.KeysView(self._raw)

	def items(self: SingleResultMixinType):
		"""A set-like object providing a view on D's items."""
		return collections.abc.ItemsView(self._raw)

	def values(self: SingleResultMixinType, attr=None, raise_nokey=False, nokey_value=None):
		"""Return all values of the given attribute as list.
		:param attr Attribute (usually as a string) - or None to get a complete ValuesView of the Result mapping items.
		:param raise_nokey True to immediately reraise catched KeyError
		:param nokey_value Value to put in for absent keys (if KeyErrors are not raised)."""
		if attr is None:
			return collections.abc.ValuesView(self._raw)
		else:
			return ResultSet.values(self, attr, raise_nokey, nokey_value)

	def __len__(self: SingleResultMixinType):
		"""Length of this sequence - this is always 1."""
		return 1

	def __iter__(self: SingleResultMixinType):
		"""Iterate of the "sequence" item (this one and only object).
		This is not useful for this class, but to avoid trouble caused by inheriting of Sequence."""
		yield self


class Result(SingleResultMixin, ResultSet):
	"""Icinga2 API request result (one from results)."""
