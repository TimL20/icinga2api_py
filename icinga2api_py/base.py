# -*- coding: utf-8 -*-
"""This module contains the representations of Icinga2 objects and other classes, that are important for
this high-level API client.
"""

from .api import API

import json
import collections.abc
import requests.exceptions


class Icinga2ApiError(Exception):
	"""Indication, that something went wrong when communicating with the Icinga2 API."""


class WrongObjectsCount(Exception):
	"""Raised when an operation requiring a particular number of objects is executed, but the number of object returned
	by Icinga is a different one.
	For example there are Operations requiring at least one object, so this exception is raised when there is no object.
	"""

class NotExactlyOne(WrongObjectsCount):
	"""Raised when an operation requiring exactly one object is executet, but there is not exactly one object."""


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
	def __init__(self, response):
		self._response = response if response else None
		self._data = None
		self._results = None

	def _load(self):
		try:
			self._data = self._response.json()
			self._results = tuple(self._data["results"])
		except json.decoder.JSONDecodeError:
			raise Icinga2ApiError("Failed to parse JSON response.")
		except KeyError:
			pass  # No "results" in _data

	@property
	def results(self):
		# TODO implement a possibility (I don't know how yet), to do some sort of timed caching of self._results...
		if self._results is None:
			self._load()
		if self._results is None:
			raise Icinga2ApiError("Failed to load results.")
		return self._results

	@property
	def loaded(self):
		return self._results is not None

	def __getattr__(self, item):
		if hasattr(self._data, item):
			return getattr(self._data, item)
		if hasattr(self._response, item):
			return getattr(self._response, item)
		return None

	def get_object(self, index):
		return Result(self.results[index])

	def __getitem__(self, index):
		return self._create_object(index)

	def __len__(self):
		return len(self.results)

	def __bool__(self):
		try:
			return bool(self.results)
		except (TypeError, KeyError, requests.exceptions.RequestException):
			return False

	###################################################################################################################
	# Enhanced access to result data ##################################################################################
	###################################################################################################################

	def get_values(self, attr):
		"""Returns all values of given attribute(s) as a list."""
		attr = (attr,) if isinstance(attr, str) else attr
		ret = []
		for r in self.results:
			for key in attr:
				r = r[key]
			ret.append(r)
		return ret

	def are_all(self, attr, expected):
		"""Returns True, if all results attributes have the expected value."""
		attr = (attr,) if isinstance(attr, str) else attr
		for r in self.results:
			for key in attr:
				r = r[key]
			if r != expected:
				return False
		return True

	def min_one(self, attr, expected):
		"""Return True, if min. one result attribute has the expected value."""
		attr = (attr,) if isinstance(attr, str) else attr
		for r in self.results:
			for key in attr:
				r = r[key]
			if r == expected:
				return True
		return False

	def min_max(self, attr, expected, min, max):
		"""Returns True, if the result attribute attr has at least min times and maximally max times the expected value"""
		attr = (attr,) if isinstance(attr, str) else attr
		i = 0
		for r in self.results:
			for key in attr:
				r = r[key]
			if r == expected:
				i += 1
				if i > max:
					return False
		return i < min

	def return_one(self):
		if len(self.results) != 1:
			raise NotExactlyOne("Required exactly one object, found %d", len(self.results))
		return self[0]  # calls __getitem__


class Icinga2Objects(Response):
	def __init__(self, query, data=None, all_joins=False):
		super().__init__(data)
		self._query = query
		self.all_joins = all_joins

	def _load(self):
		self._response = self._query(all_joins=self.all_joins)
		return super()._load()

	def load(self):
		"""Method to force loading."""
		self._load()

	def get_object(self, index):
		return super().get_object(index)


class Icinga2Object(Icinga2Objects, collections.abc.Mapping):
	def __init__(self, query, name, data=None, all_joins=False):
		super().__init__(query, data, all_joins)
		self._name = name

	@property
	def name(self):
		return self._name

	def _load(self):
		ret = super()._load()
		if len(self.results) != 1:
			raise NotExactlyOne("Required exactly one object, found %d", len(self.results))
		return ret

	def get_object(self, index=0):
		return Response.get_object(self, 0)

	def __getitem__(self, item):
		return self.get_object()[item]

	def __len__(self):
		return len(self.get_object())

	def __iter__(self):
		return iter(self.get_object())

	def __getattr__(self, item):
		ret = super().__getattr__(item)
		if ret is None:
			ret = self[item]
		return ret
