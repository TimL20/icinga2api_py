# -*- coding: utf-8 -*-
"""This module contains the basic representations of Icinga2 configuration objects.
"""

import logging

from .results import CachedResultSet, Result


class Icinga2Objects(CachedResultSet):
	"""Object representing one or more Icinga2 configuration objects.
	This class is a CachedResultSet, so a Request is used to (re)load the response its results on demand or after cache
	expiry (time in seconds)."""
	def __init__(self, request, caching, response=None):
		"""Init a Icinga2Objects representation from a request.
		:param request The request whose results are represented.
		:param caching Caching time in seconds.
		:param response Optional already loaded response for the request."""
		super().__init__(request, caching, response)

	def result_as(self, index, class_):
		"""Return result at given index as a defined type (results.Result or Icinga2Object subclass)."""
		if not issubclass(class_, Icinga2Object):  # and not isinstance(class_, Result)
			return class_(super().result(index))

		# TODO maybe it's possible without loading (if not self.loaded)?
		# Get result object
		res = super().result(index)
		# Build request for single object with filter string
		mquery = self._request.clone()
		fstring = "{}.name==\"{}\"".format(res["type"], res["name"])
		mquery.json = {"filter": fstring}
		return class_(mquery, res["name"], self._expiry, data=res)

	def result(self, index):
		"""Return the Icinga2Object at this index."""
		self.result_as(index, Icinga2Object)

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

		# TODO rewrite the following

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


class Icinga2Object(Icinga2Objects, Result):
	"""Object representing exactly one Icinga2 configuration object.
	Only the first results objects is used if the request returned more than one object.
	This class extends Icinga2Objects and Result, so it's Mapping and Sequence in one. On an iteration only the sequence
	feature is taken into account (so only this one and only object is yield)."""
	def __init__(self, request, name, caching, response=None, data=None):
		"""Init a Icinga2Object representation from a request.
		:param request The request whose results are represented.
		:param name The name of this object. This is used somewhere (not here).
		:param caching Caching time in seconds.
		:param response Optional response from this request if already loaded.
		:param data Optional the one results object (represented) from a appropriate request if already loaded."""
		super().__init__(request, caching, response)
		self.name = name
		if data is not None:
			self._results = [data]

	def result_as(self, index, class_):
		"""Overriding result_as from Icinga2Object to always return the object at index 0."""
		# TODO add a hint if the request returned more than one result - ignoring is not the best solution...
		return super().result_as(0, class_)

	def result(self, index=0):
		"""Return plain result."""
		return self.result_as(index, Result)

	def __getitem__(self, item):
		"""Implements Mapping and sequence item access in one."""
		if isinstance(item, int):
			return self.result(item)
		return self.result()[item]

	def __len__(self):
		"""Results length - this will always return None, not the real length of results from the request."""
		return 1

	def __iter__(self):
		"""Returns a generator, generating just this one and only object.
		Otherwise we may run into trouble because of the relationship to Icinga2Objects (as that's a sequence)."""
		def generator():
			yield self

		return generator()

	def __str__(self):
		return str(self.result())
