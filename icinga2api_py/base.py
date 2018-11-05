# -*- coding: utf-8 -*-
"""This module contains the representations of Icinga2 objects and other classes, that are important for
this high-level API client.
"""

from .api import API

import json
import collections.abc
import requests.exceptions
import time
import logging
import copy


class Icinga2ApiError(Exception):
	"""Indication, that something went wrong when communicating with the Icinga2 API."""


class NotExactlyOne(Exception):
	"""Raised when an operation requiring exactly one object is executed, but there is not exactly one object."""


def parseAttrs(attrs):
	"""Split attrs on dots, return attrs if it's not a string."""
	if isinstance(attrs, str):
		return attrs.split(".")
	else:
		return attrs


class Client(API):
	"""Icinga2 API client for not-streaming content."""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs, response_parser=Response)

	def add_body_parameters(self, **parameters):
		for parameter, value in parameters.items():
			self.s(parameter)(value)
		return self


class StreamClient(Client):
	"""Icinga2 API client for streamed responses."""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs, response_parser=StreamResponse)
		self.Request = StreamClient.StreamRequest

	class StreamRequest(API.Request):
		"""API Request with stream set to true for the request."""
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.request_args["stream"] = True

	@staticmethod
	def create_from_client(client):
		"""Creation of a StreamClient from a Client."""
		res = copy.copy(client)  # Create shallow copy of client
		res.Request = StreamClient.StreamRequest
		res.response_parser = StreamResponse


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

	def __str__(self):
		return str(self._data)


class StreamResponse:
	"""Access to response(s) of a streamed Icinga2 API response.
	Streamed responses are separated by new lines according to the Icinga2 API documentation."""
	def __init__(self, response):
		self._response = response

	def iter_responses(self):
		"""Iterate over responses, wich are returned as Result objects."""
		for line in self._response.iter_lines():
			yield Result(json.loads(line))


class Response(collections.abc.Sequence):
	"""Access to an Icinga2 API Response"""
	def __init__(self, response):
		self._response = response
		self._results = None

	@property
	def response(self):
		"""The received response, a requests.Response object."""
		return self._response

	def _load(self):
		"""Parses response to results and store results. It's a separate method to make overriding easy."""
		try:
			data = self.response.json()  # Works also with Response responses because of __getattr__
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
		return getattr(self.response, attr)

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

	def __str__(self):
		res = "no" if not bool(self) else len(self)
		return "<Response [{}], {} results>".format(self.response.status_code, res)

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

	@property
	def results(self):
		"""Extends the Response.results property access with timed caching. The response is reloaded when it's older
		than the configured expiry time."""
		if self._expires < time.time():
			self.load()
		return super().results

	@property
	def response(self):
		"""requests.Response object, that is the original data source from the Icinga2 API.
		The response property is used by _load() from Response, so it should not call _load().
		Loads response with use of the query passed to the constructor if necessary."""
		if self._response is None or self._expires < time.time():
			kwargs = {"all_joins": 1} if self.all_joins else {}
			res = self._query(**kwargs)
			self._response = res.response if isinstance(res, Response) else res
		if self._response is None:
			raise Icinga2ApiError("Failed to load response.")
		return self._response

	def load(self):
		"""Method to force loading."""
		self._load()
		self._expires = int(time.time()) + self._expiry

	@property
	def one(self):
		# Check object count if loaded
		if self._response is not None and len(self) != 1:
			raise NotExactlyOne("Recuired exactly one object, found {}".format(len(self)))
		return Icinga2Object(self._query, self[0]["name"], self.response)

	###################################################################################################################
	# Actions #########################################################################################################
	###################################################################################################################

	def action(self, action, **parameters):
		"""Process an action with specified parameters. This method works only, because each and every object query 
		result has object type (type) and full object name (name) for the object. It is assumed, that the type is the
		same for all objects (should be...). With this information, a filter is created, that should match all Icinga2
		objects represented."""
		if len(self) < 1:
			return None
		type = self[0]["type"].lower()
		names = [obj["name"] for obj in self]
		logging.getLogger(__name__).debug("Processing action {} for {} objects of type {}".format(action, len(names), type))
		fstring = "\" or {}.name==\"".format(type)
		fstring = "{}.name==\"{}".format(type, fstring.join(names))
		query = self._query.client.actions.s(action).filter(fstring)
		for parameter, value in parameters.items():
			query = query.s(parameter)(value)
		return query

	def modify(self, attrs):
		"""Modify this/these objects; set the given attributes (dictionary)."""
		mquery = copy.copy(self._query)  # Shallow copy of this query Request
		mquery.method = "POST"
		mquery.body = dict(self._query.body)  # copy original body (filter and such things)
		mquery.body["attrs"] = attrs  # Set new attributes
		return mquery()  # Execute modify query

	def delete(self, cascade=False):
		"""Delete this/these objects, cascade that if set to True."""
		mquery = copy.copy(self._query)  # Shallow copy of this query Request
		mquery.method = "DELETE"
		mquery.body = dict(self._query.body)  # copy original body (filter and such things)
		cascade = 1 if cascade else 0
		return mquery(cascade=cascade)  # Execute delete query


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
		"""Name of this Icinga2 object. Only singular object have a name."""
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
		if isinstance(item, int):
			return self.get_object(item)
		return self.get_object()[item]

	def __len__(self):
		return len(self.get_object())

	def __iter__(self):
		"""Iterate over the result mapping object."""
		return iter(self.get_object())

	def __str__(self):
		return str(self.get_object())

	def return_one(self):
		"""Override method of Response, to avoid trouble."""
		return self.get_object()
