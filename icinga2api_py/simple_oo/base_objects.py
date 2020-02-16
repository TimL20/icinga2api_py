# -*- coding: utf-8 -*-
"""This module contains the basic representations of Icinga2 configuration objects.
"""

import logging
from typing import Iterable

from ..results import CachedResultSet, ResultList, SingleResultMixin

LOGGER = logging.getLogger(__name__)


def objects_filter(type_: str, object_names: Iterable):
	"""Create a filter for the Icinga API that filters for the objects given by name (as sequence of strings) and
	type (just one string describing the type of all the objects).

	:returns The filter as a string, or None if filter construction was not possible.
	"""
	if not type_:
		return None
	type_ = type_.lower()
	if type_ == "service":
		# Services are objects that are specified as <host>!<service>
		host_service_pairs = (name.split('!', 1) for name in object_names)
		fstringbuilder = (
			"(host.name==\"{}\" && service.name==\"{}\")".format(host, service)
			for host, service in host_service_pairs
		)
	else:
		# Default is the simplest possible filter: <type>.name=="<name>"
		fstringbuilder = (
			"{}.name==\"{}\"".format(type_, obj)
			for obj in object_names
		)

	return " || ".join(fstringbuilder) or None


class Icinga2Objects(CachedResultSet):
	"""Object representing one or more Icinga2 configuration objects.
	This class is a CachedResultSet, so a Request is used to (re)load the response its results on demand or after cache
	expiry (time in seconds)."""

	@property
	def type(self):
		"""The Icinga object type, or None if there are no objects."""
		try:
			return self[0]["type"]
		except IndexError:
			# Maybe this is a good idea, maybe it's not... TODO think about it again
			return None

	def objects_filter(self):
		"""Get a Icinga API filter that filters for the objects of self."""
		return objects_filter(self.type, (obj["name"] for obj in self))

	def result_as(self, index, class_):
		"""Get single result at given index as a given definded type (results.Result, Icinga2Object or Icinga2Object
		subclass)."""
		if not issubclass(class_, Icinga2Object):
			# New object with result from parent class
			# Handles slicing
			return super().result(index)

		# Don't attempt to clone the request if there is no request
		has_request = self._request is not None

		# Construct Icinga2ObjectList with object of class_
		ret = list()
		for res in super().result(index):
			# Build request
			if has_request:
				req = self._request.clone()
				req.json = {"filter": objects_filter(res["type"], (res["name"],))}
			else:
				req = None
			ret.append(class_(
				request=req, results=res,
				cache_time=self.cache_time, next_cache_expiry=self._expires
			))

		lst = Icinga2ObjectList(ret)

		if isinstance(index, slice):
			return lst

		return ret[0]

	def result(self, index):
		"""Return the Icinga2Object at this index."""
		return self.result_as(index, Icinga2Object)

	###################################################################################################################
	# Actions #########################################################################################################
	###################################################################################################################

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


class ActionMixin:
	"""Mixin for Icinga2Objects subclasses supporting actions (hosts, services)."""

	def action(self: Icinga2Objects, action, **parameters):
		"""Process an action with specified parameters.

		This method works because each and every object query
		result has object type (type) and full object name (name) for the object. It is assumed, that the type is the
		same for all objects (should be...). With this information, a filter is created, that should match all Icinga2
		objects represented.
		"""
		if len(self) < 1:
			return None
		type_ = self.type
		names = (obj["name"] for obj in self)
		LOGGER.debug("Processing action {} for {} objects of type {}".format(action, len(self), type_))
		fstring = objects_filter(self.type, names)

		if not fstring:
			return None

		# self._request.api = Icinga2 (client) instance
		query = self._request.api.actions.s(action).type(type_.title()).filter(fstring)
		for parameter, value in parameters.items():
			query = query.s(parameter)(value)
		return query.post()


class Icinga2ObjectList(ResultList):
	"""List of Icinga2 configuration objects.
	The difference to Icinga2Objects is, that the objects here are really handled as single objects, whereas in
	Icinga2Objects they are handled as one results list from a request/response.
	This way it's possible to add objects to a Icinga2ObjectList.
	On the other hand, operations (actions, modify, delete) must be handled for every single object.
	A Icinga2ObjectList is built e.g. on slicing a Icinga2Objects object, or by creating it and adding objects.
	"""

	def __init__(self, results=None, result_class=None):
		# Let the result class default to Icinga2Object
		result_class = result_class or Icinga2Object
		super().__init__(results, result_class)

	# TODO add modify and delete methods


class Icinga2Object(SingleResultMixin, Icinga2Objects):
	"""Object representing exactly one Icinga2 configuration object.
	Do not use an object of this class with a request that may return more than one result. This can cause
	trouble, and as other objects than the first one are ignored it's not possible to notice.
	This class extends Icinga2Objects with the SingleResultMixin, so it's Mapping and Sequence in one.
	"""

	@property
	def name(self):
		"""Name of this Icinga2Object."""
		return self._raw["name"]
