# -*- coding: utf-8 -*-
"""This module contains the basic representations of Icinga2 configuration objects.
"""

import logging

from .results import CachedResultSet, ResultList, SingleResultMixin


class Icinga2Objects(CachedResultSet):
	"""Object representing one or more Icinga2 configuration objects.
	This class is a CachedResultSet, so a Request is used to (re)load the response its results on demand or after cache
	expiry (time in seconds)."""

	def result_as(self, index, class_):
		"""Get single at given index result as a definded type (results.Result, Icinga2Object or Icinga2Object subclass)."""
		if not issubclass(class_, Icinga2Object):
			# New object with result from parent class
			# Handles slicing
			return super().result(index)

		if isinstance(index, slice):
			# Icinga2ObjectList with object of class_
			ret = Icinga2ObjectList()
			for obj in super().result(index):
				# Build request
				req = self._request.clone()
				req.json = {"filter": "{}.name==\"{}\"".format(obj["type"], obj["name"])}
				ret.append(class_(req, obj["name"], self.cache_time, results=obj, next_cache_expiry=self._expires))
			return ret

		# Get result object
		res = super().result(index)
		# Build request for single object with filter string
		mquery = self._request.clone()
		fstring = "{}.name==\"{}\"".format(res["type"].lower(), res["name"])
		mquery.json = {"filter": fstring}
		return class_(mquery, res["name"], self.cache_time, results=res, next_cache_expiry=self._expires)

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
		objects represented.
		As there is no action specified in the documentation, that applies to other objects than hosts or services, this
		method will only handle hosts and services."""
		if len(self) < 1:
			return None
		type = self[0]["type"].lower()
		names = [obj["name"] for obj in self]
		logging.getLogger(__name__).debug("Processing action {} for {} objects of type {}".format(action, len(names), type))
		if type == "host":
			# Hosts filters are quite simple
			fstring = "host.name==\"{}\"".format("\" || host.name==\"".join(names))
		elif type == "service":
			# Services are objects that are specified as <host>!<service>
			host_service_pairs = [name.split('!', 1) for name in names]
			fstringbuilder = [
				"(host.name==\"{}\" && service.name==\"{}\")".format(host, service)
				for host, service in host_service_pairs
			]
			fstring = " || ".join(fstringbuilder)
		else:
			raise ValueError("Action on objects only allowed for host or service object")

		if not fstring:
			return None

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
	A Icinga2ObjectList is built e.g. on slicing a Icinga2Objects object, or by creating it and adding objects.
	"""

	# Here the implementations of action(), modify() and delete() as in Icinga2Objects should go...


class Icinga2Object(SingleResultMixin, Icinga2Objects):
	"""Object representing exactly one Icinga2 configuration object.
	Do not use an object of this class with a request that may return more than one result. This can cause
	trouble, and as other objects than the first one are ignored it's not possible to notice.
	This class extends Icinga2Objects with the SingleResultMixin, so it's Mapping and Sequence in one.
	"""

	def __init__(self, results=None, response=None, request=None, json_kwargs=None):
		"""Init a Icinga2Object representation from a request.
		:param results Optional the one results object (represented) from a appropriate request if already loaded
		:param request The request whose results are represented
		:param response Optional response from this request if already loaded
		"""
		super().__init__(results, response, request, json_kwargs)

	@property
	def name(self):
		"""Name of this Icinga2Object."""
		return self._raw["name"]
