# -*- coding: utf-8 -*-
"""
This module contains all relevant stuff regarding the results attribute of an Icinga2 API response.
"""

import collections.abc
import time
import typing


class ResultSet(collections.abc.Sequence):
	"""Represents a set of results returned from the Icinga2 API.

	Unlike the name suggests, this "set" is actually a (immutable) sequence. Think of it as a tuple of Result objects.
	The class provides methods that are useful as-is, and some that are made to be overridden in subclasses.
	"""

	def __init__(self, results=None):
		"""Init a ResultSet.

		:param results: A sequence of results (dict objects as from the API), or None to call the load() method when
			getting the results.
		"""
		self._results = results

	def load(self):
		"""Load results.

		This method is here to be overriden. It's required that this method sets _results to be a sequence (default is
		None). This implementation initialises the internal results with an empty tuple.
		"""
		self._results = tuple()

	@property
	def results(self):
		"""Sequence of results as dict objects (as from the API).

		This method is meant for internal use, but could also be used from the outside. It returns the protected
		internal results, but will call the load() method if they are not loaded yet. (default).
		:return: Sequence of results as dict objects.
		"""
		if not self.loaded:
			self.load()
		return self._results

	@property
	def loaded(self):
		"""True if the results are loaded.

		The results are considered loaded if they are not None. Note that this criterion could change in the future.
		"""
		return self._results is not None

	def result(self, index):
		"""Return result at the given index, or an appropriate ResultSet for a slice.

		This method is called from __getitem__, and behaves exactly like this method should behave for a sequence.
		:param index: Integer for one result or slice for a result that.
		:return: A Result represented from the given indix, or a ResultSet for the given slice.
		"""
		if isinstance(index, slice):
			return ResultSet(self.results[index])
		return Result(self.results[index])

	def __getitem__(self, index):
		"""Return a result at the given index, or an appropriate ResultSet for a slice, also see result()."""
		return self.result(index)

	def __len__(self):
		"""Length of the results sequence."""
		return len(self.results)

	def __bool__(self):
		"""Return True if results not empty."""
		return bool(self.results)

	def __eq__(self, other):
		"""True if the value of the results property is equal to that of the other object."""
		try:
			return self.results == other.results
		except AttributeError:
			return NotImplemented

	def __str__(self):
		"""Return short string representation."""
		res = "?" if not self.loaded else "no" if not len(self) else len(self)
		return "<{} with {} results>".format(self.__class__.__name__, res)

	###################################################################################################################
	# Enhanced access to result data ##################################################################################
	###################################################################################################################

	@staticmethod
	def parse_attrs(attrs):
		"""Parse attrs string: split attrs at dots."""
		try:
			return attrs.split('.')
		except AttributeError:
			return attrs

	def fields(self, key, raise_nokey=False, nokey_value=None):
		"""Yield all values the results have for a given key.

		:param key: The key for which to get the values of the results (usually as a string).
		:param raise_nokey: True to use immediately re-raise the catched KeyError when a result does not have the
			required key.
		:param nokey_value: Value to use when a result does not have the required key. Has no effect if raise_nokey is
			True.
		"""
		key = self.parse_attrs(key)
		for res in self.results:
			for subkey in key:
				try:
					res = res[subkey]
				except (KeyError, TypeError):
					# KeyError if no such key, TypeError if res is not a dict/Mapping
					if raise_nokey:
						raise KeyError("No such key")
					else:
						res = nokey_value
						break
			yield res

	def where(self, key, expected, cls=None):
		"""Return a ResultSet with the results that all have a certain value for a given key.
		
		The returned object is created with the cls parameter, so a class the return value should be a type of can be
		passed there (cls needs to behave like the ResultSet constructor to work of course).
		A overridden or a future version of this method may support more filter expressions than comparison for
		equality.

		:param key: The key for the fields of the results that should be tested against the expected.
		:param expected: The expected value, only results that have this value for mapped to the key are returned.
		:param cls: The class for the returned object, None (default) for a ResultSet. Could also be any other callable.
		:return: A ResultSet (or another type when the cls parameter is used) with all results of this one, that have
			the expected value for a certain key.
		"""
		key = self.parse_attrs(key)
		cls = cls or ResultSet
		ret = []
		for res in self.results:
			r = res
			for subkey in key:
				try:
					r = r[subkey]
				except (KeyError, TypeError):
					r = KeyError
					break
			if r == expected:
				ret.append(res)
		return cls(ret)

	def number(self, key, expected):
		"""Return number of results having an expected value.

		:param key: The key for the fields of the results for which the values are compared aginst the expected value.
		:param expected: An expected value.
		:return: Number of results that have a certain value for a given key.
		"""
		cnt = 0
		for value in self.fields(key, nokey_value=KeyError):
			if value == expected:
				cnt += 1
		return cnt

	def all(self, key, expected):
		"""Return True if all results have the expected value for a certain key.

		:param key: The key for the results fields.
		:param expected: The expected value to look for in the results fields.
		:return: True if all results have the expected value mapped to a certain key, False otherwise.
		"""
		return all((value == expected for value in self.fields(key, nokey_value=KeyError)))

	def any(self, key, expected):
		"""Return True if any result has the expected value for a certain key.

		:param key: The key for the results fields.
		:param expected: The expected value to look for in the results fields.
		:return: True if any results has the expected value mapped to a certain key, False otherwise.
		"""
		return any((value == expected for value in self.fields(key, nokey_value=KeyError)))

	def min_max(self, key, expected, min_num, max_num):
		"""Return True, if at minimum *min_num* and at maximum *max_num* results have an expected value for a given key.

		:param key: The key for the results fields.
		:param expected: The expected value to look for in the results fields.
		:param min_num: Minimum number.
		:param max_num: Maximum number.
		:return: True if the count of fields that have the expected value is `>=` min_num and `<=` max_num.
		"""
		cnt = 0
		for value in self.fields(key, nokey_value=KeyError):
			if value == expected:
				cnt += 1
				if cnt > max_num:
					return False
		return cnt >= min_num


class ResultsFromResponse(ResultSet):
	"""ResultSet from a given APIResponse."""

	def __init__(self, results=None, response=None, json_kwargs=None):
		"""Init a ResultsFromResponse object.

		Usually you want to call the init with only the response parameter given.
		:param results: Already loaded results, or None (default).
		:param response: The response to get the results from (if results are None, which is the default). Passing None
			here does not make sense, as basically everything will fall back to the ResultSet default implementations.
		:param json_kwargs: Optional a dictionary of keyword arguments to pass for json decoding of the results when
			getting them from the response. None for no keyword arguments to pass.
		"""
		super().__init__(results)
		self._response = response
		self._json_kwargs = json_kwargs or dict()

	@property
	def response(self):
		"""The used to construct this object (should be an APIResponse as from the Icinga API)."""
		return self._response

	def load(self):
		"""Get results from the response (JSON decoded)."""
		try:
			self._results = self.response.results(**self._json_kwargs)
		except AttributeError:
			# Especially in the case, that the response is None
			super().load()

	def __str__(self):
		"""Return short string representation."""
		if self.loaded:
			res = len(self) or "no"
			return "<{} with {} results, status {}".format(self.__class__.__name__, res, self.response.status_code)
		else:
			return "<{}, not loaded currently>".format(self.__class__.__name__)


class ResultsFromRequest(ResultsFromResponse):
	"""ResultSet loaded on demand from a given request."""

	def __init__(self, results=None, response=None, request=None, json_kwargs=None):
		"""Init a ResultsFromRequest object.
		
		:param results: Already loaded results, or None (default).
		:param response: An already loaded APIResponse to get the results from. The response object will be loaded on
			demand when None is passed as the response (default).
		:param request: An APIRequest to load the response (and therefore results) from.
		:param json_kwargs: Optional a dictionary of keyword arguments to pass for json decoding of the results when
			getting them from the response. None for no keyword arguments to pass.
		"""
		super().__init__(results, response, json_kwargs)

		# If the request is None, act like it always loads the response (that being None is handled in super's load)
		# If the request is not None, the response is loaded via the APIRequest
		# and the results are loaded from the response
		# - which is actually the point of this class, the other stuff is only to be behave like the parent classes
		self._request_lambda = request if request is not None else lambda: response
		self._request = request

	@property
	def request(self):
		"""The request of this ResultsFromRequest object."""
		return self._request

	@property
	def response(self):
		"""Loads response with use of the request - this property is ironically called from the load method."""
		if self._response is None:
			try:
				self._response = self._request()
			except TypeError:
				# In case the request is None
				self._response = self._request_lambda()

		return self._response

	def load(self):
		"""Reload the results from the response, and the response from the request."""
		self._response = None
		super().load()

	def __eq__(self, other):
		"""True if other has the same request, or the superclass's __eq__ returns True."""
		try:
			return self.request == other.request or super().__eq__(other)
		except AttributeError:
			return NotImplemented


class CachedResultSet(ResultsFromRequest):
	"""ResultSet from a request, with load on demand and caching.

	The underlying results are loaded on demand from the request, and also every time the last load was more time ago
	than allowed with the cache_time property. Be aware of the fact, that the data in this object could change every
	time they're accessed.
	The hold mechanism was created to temporarily disable cache reloading, drop() will re-enable it. This mechanism is
	also used when using a CachedResultSet as a context manager.
	"""

	def __init__(self, results=None, response=None, request=None, cache_time=float("inf"), next_cache_expiry=None,
				timefunc=time.time, json_kwargs=None):
		"""ResultSet from Request with caching.

		:param results: Already loaded results, or None (default).
		:param response: An already loaded APIResponse to get the results from. The response object will be loaded on
			demand when None is passed as the response (default), and it will be reloaded on every cache time expiry
			anyway.
		:param request: An APIRequest to load the response (and therefore results) from.
		:param cache_time: How long to cache the results before reloading them.
		:param next_cache_expiry: Sets the next cache expiry (absolute time in seconds).
		:param timefunc: A callable to use for getting the current time (to determine when to reload cache), defaults
			to ``time.time``
		:param json_kwargs: Optional a dictionary of keyword arguments to pass for json decoding of the results when
			getting them from the response. None for no keyword arguments to pass.
		"""
		super().__init__(results, response, request, json_kwargs)
		self.timefunc = timefunc
		self.cache_time = cache_time
		self._expires = next_cache_expiry or cache_time
		# Holds the _expires attribute value on hold
		self._hold = None

	@property
	def response(self):
		"""The original response from the Icinga2 API, reload the response on cache expiry."""
		if self._expires < self.timefunc():
			# Delete cached response
			self._response = None
		return super().response

	def load(self):
		"""(Re)load results from request/response and reset cache expiry."""
		super().load()
		self._expires = self.timefunc() + self.cache_time

	@property
	def results(self):
		"""Extends results access with timed caching."""
		if self._expires < self.timefunc():
			self._results = None
		return super().results

	@property
	def loaded(self):
		"""True if a successful load has taken place and cache is not expired."""
		return super().loaded and self._expires >= self.timefunc()

	def invalidate(self):
		"""Delete cached response and results."""
		self._response = None
		self._results = None

	def fixed(self):
		"""Get a ("fixed") ResultSet with the results of this CachedResultSet.

		Basically this means to get almost the same object without a cache.	This is in some situations better than the
		hold mechanism, althought the purpose is very similar.
		"""
		return ResultSet(self.results)

	def hold(self):
		"""Set cache expiry to infinite to suppress reload by cache expiry.

		Call drop() to undo this, the old cache expiry value is stored until drop.
		"""
		if self.held:
			raise ValueError("Cannot hold twice.")

		self._hold = self._expires
		self._expires = float("inf")

	def drop(self):
		"""Undo hold - cache expiry is set to the old value."""
		if self._hold is None:
			raise ValueError("Cannot drop without hold.")

		self._expires = self._hold
		self._hold = None

	@property
	def held(self):
		"""Whether or not the object is "hold", meaning hold was called without drop."""
		return self._hold is not None

	def __enter__(self):
		"""Suppress reload on cache expiry (hold)."""
		self.hold()

	def __exit__(self, exc_type, exc_val, exc_tb):
		"""Re-enable reload on cache expiry (drop)."""
		self.drop()


class ResultList(ResultSet, collections.abc.MutableSequence):
	"""Mutable results representation, with all nice features of ResultSet."""

	def __init__(self, results=None, result_class=None):
		"""A ResultList can be initiated with a sequence of mapping objects or one mapping object."""
		super().__init__(None)
		if not isinstance(results, collections.abc.Sequence):
			results = list() if not results else [dict(results)]
		self._results = list(results)

		#: A callable (e.g. class) used to create a single result
		self.result_class = result_class or Result

	def result(self, index):
		"""Return result at the given index, or a ResultSet."""
		if isinstance(index, slice):
			return self.__class__(self.results[index])

		# Return this result, wrapped via result_class if needed
		result = self.results[index]
		try:
			if isinstance(result, self.result_class):
				# Directly return the result
				return result
		except TypeError:
			# Catched to allow result_class to be any callable
			pass

		try:
			# In case the appended result something like a Result object (although not a subclass of result_class)
			result = result.results
		except AttributeError:
			pass

		return self.result_class(result)

	def __delitem__(self, index):
		del self.results[index]

	def __setitem__(self, index, value):
		try:
			# Assume it's a Result object
			self.results[index] = value.result(0)
		except AttributeError:
			# Set the raw value...
			self.results[index] = value

	def insert(self, index, value):
		try:
			# Assume it's a Result object
			self.results.insert(index, value.result)
		except AttributeError:
			# Insert the raw value...
			self.results.insert(index, value)


# Type for self of the SingleResultMixin
SingleResultMixinType = typing.Union["SingleResultMixin", ResultSet]


class SingleResultMixin:
	"""Mixin for ResultSet to represent exactly one instead of any number of results.

	This class appears as a sequence with length one, but also as an immutable Mapping.
	"""

	@property
	def results(self: SingleResultMixinType):
		"""Sequence of exactly one result."""
		# Get the results like the class this mixin is used with would
		results = super().results

		# Return a sequence with exactly one item, no matter which type the results have
		if results is None:
			return tuple()
		if isinstance(results, collections.abc.Sequence):
			try:
				return results[0],
			except IndexError:
				return tuple()

		# Handle the case special for classes using this mixin, that a single result is loaded/given
		return results,

	@property
	def _raw(self: SingleResultMixinType):
		"""Get the "raw" result as a dictionary. Meant for internal use only."""
		try:
			return self.results[0]
		except IndexError:
			# Behave like an empty dict, e.g. when keys() is called
			return dict()

	@staticmethod
	def attr_value(attrs, obj):
		"""Get the attr value of an object.

		:param attrs: Sequence of items to access recursively
		:param obj: The Mapping object from where to access the attr values
		:return: obj[attrs[0]][attrs[1]]...[attrs[len(attrs)-1]]
		:raises: KeyError if further mapping access was not possible.
		"""
		item = attrs
		try:
			for item in attrs:
				obj = obj[item]
			return obj
		except (KeyError, ValueError):
			raise KeyError(f"No such key: {item}")

	def __getitem__(self: SingleResultMixinType, item):
		"""Implements Mapping and sequence access in one."""
		if isinstance(item, int) or isinstance(item, slice):
			return self.result(item)

		# Mapping access: Get attr of raw result
		return self.attr_value(self.parse_attrs(item), self._raw)

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

	def values(self: SingleResultMixinType):
		"""Get a ValuesView for the result mapping items."""
		return collections.abc.ValuesView(self._raw)


class Result(SingleResultMixin, ResultSet, collections.abc.Mapping):
	"""Icinga2 API request result (one from results)."""
