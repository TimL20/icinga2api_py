# -*- coding: utf-8 -*-
"""This module contains the representations of Icinga2 objects and other classes, that are important for
this high-level API client.
"""

from .api import API

import json
import collections.abc
import requests.exceptions
import time
import copy


class Icinga2ApiError(Exception):
	"""Indication, that something went wrong when communicating with the Icinga2 API."""


class WrongObjectsCount(Exception):
	"""Raised when an operation requiring a particular number of objects is executed, but the number of object returned
	by Icinga is a different one.
	For example there are Operations requiring at least one object, so this exception is raised when there is no object.
	"""

class NotExactlyOne(WrongObjectsCount):
	"""Raised when an operation requiring exactly one object is executet, but there is not exactly one object."""


def parseAttrs(attrs):
	if isinstance(attrs, str):
		return attrs.split(".")
	else:
		return attrs


class Client(API):
	"""Icinga2 API client."""
	def __init__(self, host, auth, port=5665, uri_prefix='/v1', verify=False):
		super().__init__(host, auth, port, uri_prefix, verify, response_parser=Response)


class Result(collections.abc.Mapping):
	"""Icinga2 API request result (one from results).
	Basically just provides (read-only) access to the data of a dictionary."""
	def __init__(self, res):
		self._data = res

	def __getitem__(self, item):
		return self._data[item]

	def __getattr__(self, item):
		return self[item]

	def __len__(self):
		return len(self._data)

	def __iter__(self):
		return iter(self._data)


class Response(collections.abc.Sequence):
	"""Access to an Icinga2 API Response"""
	def __init__(self, response):
		self._response = response if response else None
		self._results = None

	@property
	def response(self):
		"""The received response, a requests.Response object."""
		return self._response

	def _load(self):
		"""Parses response to results and store results. It's a separate method to make overriding easy."""
		try:
			data = self._response.json()  # Works also with Response responses because of __getattr__
			self._results = tuple(data["results"])
		except json.decoder.JSONDecodeError:
			raise Icinga2ApiError("Failed to parse JSON response.")
		except KeyError:
			pass  # No "results" in _data

	@property
	def results(self):
		"""Returns the parsed results of response, loads that (_load) if needed."""
		if self._results is None:
			self._load()
		if self._results is None:
			raise Icinga2ApiError("Failed to load results.")
		return self._results

	@property
	def loaded(self):
		"""If the results have ever been loaded. That it returns True does not mean, that the results aren't loaded the
		next time they are requested."""
		return self._results is not None

	def get_object(self, index):
		"""An object representing one result (at the given index)."""
		return Result(self.results[index])

	def __getattr__(self, attr):
		"""Try to get a not existing attribute from the response object instead."""
		return getattr(self._response, attr)

	def __getitem__(self, index):
		"""One result at the given index."""
		return self.get_object(index)

	def __len__(self):
		"""The length of the result sequence."""
		return len(self.results)

	def __bool__(self):
		"""True if results where loaded AND there is minimum one result AND there occured no error during this check."""
		try:
			return bool(self.results)
		except (TypeError, KeyError, requests.exceptions.RequestException):
			return False

	###################################################################################################################
	# Enhanced access to result data ##################################################################################
	###################################################################################################################

	def values(self, attr):
		"""Returns all values of given attribute(s) as a list."""
		attr = parseAttrs(attr)
		ret = []
		for r in self.results:
			for key in attr:
				r = r[key]
			ret.append(r)
		return ret

	def are_all(self, attr, expected):
		"""Returns True, if all results attributes have the expected value."""
		attr = parseAttrs(attr)
		for r in self.results:
			for key in attr:
				r = r[key]
			if r != expected:
				return False
		return True

	def min_one(self, attr, expected):
		"""Return True, if min. one result attribute has the expected value."""
		attr = parseAttrs(attr)
		for r in self.results:
			for key in attr:
				r = r[key]
			if r == expected:
				return True
		return False

	def min_max(self, attr, expected, min, max):
		"""Returns True, if the result attribute attr has at least min times and maximally max times the expected value.
		The method does not necessarily look at all attributes."""
		attr = parseAttrs(attr)
		i = 0
		for r in self.results:
			for key in attr:
				r = r[key]
			if r == expected:
				i += 1
				if i > max:
					return False
		return i >= min

	def return_one(self):
		"""One result object. Raises an exception, if there is not only one result."""
		if len(self.results) != 1:
			raise NotExactlyOne("Required exactly one object, found %d", len(self.results))
		return self[0]  # calls __getitem__


class Icinga2Objects(Response):
	"""Object representing more than one Icinga2 object.
	This class uses a query when it needs to (re)load the response (and results). It is possible to load with all joins,
	if the used query accepts all_joins as a parameter. The loaded data are cached for a cache_time. Set that to zero to
	disable caching, set it to float("inf") to load only once."""
	def __init__(self, query, data=None, all_joins=False, cache_time=60):
		"""Constructs the representation of Icinga2 objects.
		query -> Query used to load all data. Could be None if data is set and cache_time is float("inf").
		data -> Passed loaded data for these objects. Passing odd things here could result into funny behavior.
		all_joins -> set to true, to load object with all possible joins.
		cache_time -> data are reloaded if they are older than this cache_time."""
		super().__init__(data)
		self._query = query
		self.all_joins = all_joins
		self._expiry = cache_time
		self._expires = cache_time

	def _load(self):
		"""Loads response with the use of the query passed to the constructor."""
		kwargs = {"all_joins": 1} if self.all_joins else {}
		res = self._query(**kwargs)
		self._response = res.response if isinstance(res, Response) else res  # TODO ????
		return super()._load()

	@property
	def results(self):
		"""Extends the Response.results property access with timed caching. The response is reloaded when it's older
		than the configured expiry time."""
		if self._expires < time.time():
			self.load()
		return super().results

	def load(self):
		"""Method to force loading."""
		self._load()
		self._expires = int(time.time()) + self._expiry

	def modify(self, attrs):
		mquery = copy.copy(self._query)  # Shallow copy of this query Request
		mquery.method = "POST"
		mquery.body = dict(self._query.body)  # copy original body (filter and such things)
		mquery.body["attrs"] = attrs  # Set new attributes
		return mquery()  # Execute modify query

	def delete(self, cascade):
		mquery = copy.copy(self._query)  # Shallow copy of this query Request
		mquery.method = "DELETE"
		mquery.body = dict(self._query.body)  # copy original body (filter and such things)
		cascade = 1 if cascade else 0
		return mquery(cascade=cascade)  # Execute modify query


class Icinga2Object(Icinga2Objects, collections.abc.Mapping):
	"""Object representing exactly one Icinga2 object. It is possible to load with all joins,
	if the used query accepts all_joins as a parameter. The loaded data are cached for a cache_time. Set that to zero to
	disable caching, set it to float("inf") to load only once."""
	def __init__(self, query, name, data=None, all_joins=False, cache_time=60):
		"""Constructs the representation of an Icinga2 object.
		query -> Query used to load all data. Could be None if data is set and cache_time is float("inf").
		name -> Name of this object.
		data -> Passed loaded data for this object. Passing odd things here could result into funny behavior.
		all_joins -> set to true, to load object with all possible joins.
		cache_time -> data are reloaded if they are older than this cache_time."""
		super().__init__(query, data, all_joins, cache_time)
		self._name = name

	@property
	def name(self):
		"""Name of this object."""
		return self._name

	def _load(self):
		"""Loads the object, raises an exception if not exactly one object was returned from the query."""
		ret = super()._load()
		if len(self._results) != 1:
			raise NotExactlyOne("Required exactly one object, found %d", len(self._results))
		return ret

	def get_object(self, index=0):
		"""Get an object representing the result."""
		return Response.get_object(self, 0)

	def __getitem__(self, item):
		return self.get_object()[item]

	def __len__(self):
		return len(self.get_object())

	def __iter__(self):
		"""Iterate over the result mapping object."""
		return iter(self.get_object())

	def return_one(self):
		"""Override method of Response, to avoid trouble."""
		return self.get_object()
