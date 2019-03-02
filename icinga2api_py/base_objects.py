# -*- coding: utf-8 -*-
"""This module contains the basic representations of Icinga2 configuration objects.
"""

import logging

import collections.abc
from .results import CachedResultSet, ResultList, Result


class Icinga2Objects(CachedResultSet):
	"""Object representing one or more Icinga2 configuration objects.
	This class is a CachedResultSet, so a Request is used to (re)load the response its results on demand or after cache
	expiry (time in seconds)."""
	def __init__(self, request, cache_time, response=None, results=None):
		"""Init a Icinga2Objects representation from a request.
		:param request The request whose results are represented.
		:param cache_time Caching time in seconds.
		:param response Optional already loaded response for the request.
		:param results Optional already loaded results."""
		super().__init__(request, cache_time, response, results)

	def result_as(self, index, class_):
		"""Get single at given index result as a definded type (results.Result, Icinga2Object or Icinga2Object subclass)."""
		if not issubclass(class_, Icinga2Object):
			# New object with result from parent class
			# Handles slicing
			return super().result(index)

		if isinstance(index, slice):
			# Icinga2ObjectList with object of class_
			return Icinga2ObjectList([class_(obj) for obj in super().results[index]])

		# Get result object
		res = super().result(index)
		# Build request for single object with filter string
		mquery = self._request.clone()
		fstring = "{}.name==\"{}\"".format(res["type"], res["name"])
		mquery.json = {"filter": fstring}
		return class_(mquery, res["name"], self.cache_time, results=res)

	def result(self, index):
		"""Return the Icinga2Object at this index."""
		return self.result_as(index, Icinga2Object)

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

		# self._request.api = Icinga2 (client) instance
		query = self._request.api.actions.s(action).type(type.title()).filter(fstring)
		for parameter, value in parameters.items():
			query = query.s(parameter)(value)
		return query.post()

	def modify(self, attrs, no_invalidate=False):
		"""Modify this/these objects; set the given attributes (dictionary).
		Optionally avoid calling invalidate() with no_invalidate=True."""
		# Copy and modify the request from which these results were loaded
		mquery = self._request.clone()
		mquery.method_override = "POST"
		body = dict(mquery.json)  # Copy original body (filters, ...)
		body["attrs"] = attrs  # Set new attributes
		mquery.json = body
		ret = mquery()  # Execute modify query
		if not no_invalidate:
			self.invalidate()  # Reset cache to avoid caching something wrong
		return ret  # Return query result

	def delete(self, cascade=False, no_invalidate=False):
		"""Delete this/these objects, cascade that if set to True.
		Optionally avoid calling invalidate() with no_invalidate=True."""
		# Copy and modify the request from which these results were loaded
		mquery = self._request.clone()
		mquery.method_override = "DELETE"
		cascade = 1 if cascade else 0
		ret = mquery(cascade=cascade)  # Execute delete query
		if not no_invalidate:
			self.invalidate()  # Reset cache
		return ret  # Return query result


class Icinga2ObjectList(ResultList):
	"""List of Icinga2 configuration objects.
	The difference to Icinga2Objects is, that the objects here are really handled as single objects, whereas in
	Icinga2Objects they are handled as one results list from a request/response.
	This way it's possible to add objects to a Icinga2ObjectList.
	On the other hand, operations (actions, modify, delete) must be handled for every single object.
	A Icinga2ObjectList is built on slicing a Icinga2Objects object."""


class Icinga2Object(Result, Icinga2Objects):
	"""Object representing exactly one Icinga2 configuration object.
	Do not use an object of this class with a request, that may or may not return more than one result. This can cause
	trouble, and as other objects than the first one are ignored you won't notice!
	This class extends Icinga2Objects and Result, so it's Mapping and Sequence in one. On an iteration only the sequence
	feature is taken into account (so only this one and only object is yield)."""
	def __init__(self, request, name, cache_time, response=None, results=None):
		"""Init a Icinga2Object representation from a request.
		:param request The request whose results are represented.
		:param name The name of this object. This is used somewhere (not here).
		:param cache_time Caching time in seconds.
		:param response Optional response from this request if already loaded.
		:param results Optional the one results object (represented) from a appropriate request if already loaded."""
		# Call super init of Result
		super().__init__(results)
		# Call other super init
		Icinga2Objects.__init__(self, request, cache_time, response, results)
		self.name = name

	def result_as(self, index, class_):
		"""Overriding result_as from Icinga2Object to always return the object at index 0."""
		return Icinga2Objects.result_as(self, 0, class_)

	def result(self, index=0):
		"""Return plain result."""
		return self.result_as(index, Result)
