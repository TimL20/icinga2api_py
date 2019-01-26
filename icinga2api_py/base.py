# -*- coding: utf-8 -*-
"""This module contains the representations of Icinga2 objects and other classes, that are important for
this high-level API client.
"""

from .api import API

import json
import collections.abc
import time
import logging
import copy


class Icinga2ApiError(Exception):
	"""Indication, that something went wrong when communicating with the Icinga2 API."""


class NotExactlyOne(Exception):
	"""Raised when an operation requiring exactly one object is executed, but there is not exactly one object."""


class Client(API):
	"""Icinga2 API client for not-streaming content."""
	def __init__(self, host, auth=None, port=5665, uri_prefix='/v1', **sessionparams):
		super().__init__(host, auth, port, uri_prefix, response_parser=Response, **sessionparams)


class StreamClient(Client):
	"""Icinga2 API client for streamed responses."""
	def __init__(self, host, auth=None, port=5665, uri_prefix='/v1', **sessionparams):
		super().__init__(host, auth, port, uri_prefix, response_parser=StreamResponse, **sessionparams)
		self.session.stream = True

	@staticmethod
	def create_from_client(client):
		"""Creation of a StreamClient from a Client."""
		res = copy.copy(client)  # Create shallow copy of client
		res.Request = StreamClient.StreamRequest
		res.response_parser = StreamResponse


class StreamResponse:
	"""Access to response(s) of a streamed Icinga2 API response.
	Streamed responses are separated by new lines according to the Icinga2 API documentation."""
	def __init__(self, response):
		self._response = response

	def iter_responses(self):
		"""Iterate over responses, wich are returned as Result objects."""
		for line in self._response.iter_lines():
			yield Result(json.loads(line))


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

	def invalidate(self):
		"""To point out, that the cached response is propably not valid anymore.
		Currently, this method will set expired of the cache mechanism to the past."""
		self._expires = 0

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
		fstring = "{}.name==\"{}\"".format(type, fstring.join(names))
		# self._query.api = Icinga2 instance, property client for base.Client instance
		query = self._query.api.client.actions.s(action).type(type.title()).filter(fstring)
		for parameter, value in parameters.items():
			query = query.s(parameter)(value)
		return query.post()

	def modify(self, attrs, no_invalidate=False):
		"""Modify this/these objects; set the given attributes (dictionary).
		Optionally avoid calling invalidate() with no_invalidate=True."""
		# TODO This is not an elegant way to do this, there may be a better one?!
		# First copy some things that may be overwritten
		mquery = copy.copy(self._query)
		mquery.request = copy.copy(mquery.request)
		mquery.request.headers = copy.copy(mquery.request.headers)
		mquery.request.headers['X-HTTP-Method-Override'] = "POST"
		body = dict(self._query.request.json)  # copy original body (filter and such things)
		body["attrs"] = attrs  # Set new attributes
		mquery.request.json = body
		ret = mquery()  # Execute modify query
		if not no_invalidate:
			self.invalidate()  # Reset cache to avoid caching something wrong
		return ret  # Return query result

	def delete(self, cascade=False, no_invalidate=False):
		"""Delete this/these objects, cascade that if set to True.
		Optionally avoid calling invalidate() with no_invalidate=True."""
		# TODO This is not an elegant way to do this, there may be a better one?!
		# First copy some things
		mquery = copy.copy(self._query)
		mquery.request.headers = copy.copy(mquery.request.headers)
		mquery.request.headers['X-HTTP-Method-Override'] = "DELETE"
		mquery.request.json = copy.copy(mquery.request.json)
		mquery.request.json = dict(self._query.request.json)  # copy original body (filter and such things)
		cascade = 1 if cascade else 0
		ret = mquery(cascade=cascade)  # Execute delete query
		if not no_invalidate:
			self.invalidate()  # Reset cache
		return ret  # Return query result


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
			raise NotExactlyOne("Required exactly one object, found %d" % len(self._results))
		return ret

	def get_object(self, index=0):
		"""Get an object representing the result."""
		return Response.get_object(self, 0)

	def __getitem__(self, item):
		if isinstance(item, int):
			return self.get_object(item)
		return self.get_object()[item]

	def __getattr__(self, attr):
		if attr in self.results[0]:
			return self.results[0][attr]
		else:
			return super().__getattr__(attr)

	def __len__(self):
		return len(self.get_object())

	def __iter__(self):
		"""Returns a generator, generating just this one and only object.
		Otherwise we may run into trouble because of the relationship to Icinga2Objects."""
		def generator():
			yield self

		return generator()

	def __str__(self):
		return str(self.get_object())

	def return_one(self):
		"""Override method of Response, to avoid trouble."""
		return self.get_object()
