# -*- coding: utf-8 -*-
"""This module contains funcionality for all mapped objects.

The classes for the mapped Icinga objects are created in the types module, but every class created there inherits from
a class here.
No thread-safety (yet)."""

import json

from .exceptions import NoUserView, NoUserModify
from ..results import ResultSet, CachedResultSet, Result
from .base import Number
from .attribute_value_types import JSONResultEncoder, JSONResultDecodeHelper

# Possible keys of an objects query result
OBJECT_QUERY_RESULT_KEYS = {"name", "type", "attrs", "joins", "meta"}


class IcingaObjects(ResultSet):
	"""Base class of every representation of any number of Icinga objects that have the same type."""

	# The DESC is overriden in subclasses with the Icinga type description
	DESC = {}
	# The FIELDS is overriden in subclasses with all FIELDS and their description for the object type (incl. from parents)
	FIELDS = {}

	def __init__(self, value_sequence=None):
		"""Init Objects with a sequence of the Objects "values"."""
		super().__init__(value_sequence)

	def result(self, index):
		"""Return an appropriate IcingaObject or (in case of a slice) IcingaObjects object."""
		if isinstance(index, slice):
			return IcingaObjects(self.results[index])
		return IcingaObject((self.results[index],))


class IcingaObject(Result, IcingaObjects):
	"""Representation of exactly one Icinga object."""
	def __init__(self, value_sequence=None, value=None):
		value_sequence = value_sequence or ((value, ) if value is not None else tuple())
		IcingaObjects.__init__(value_sequence)
		super().__init__(value_sequence)


class IcingaConfigObjects(CachedResultSet, IcingaObjects):
	"""Representation of any number of Icinga objects that have the same type.
	This is the parent class of all dynamically created Icinga configuration object type classes."""

	def __init__(self, session, request, response=None, results=None, next_cache_expiry=None):
		super().__init__(request, session.cache_time, response, results, next_cache_expiry)
		self._session = session

		# JSON Decoding
		self._json_kwargs["object_pairs_hook"] = JSONResultDecodeHelper(self).object_pairs_hook

	@property
	def session(self):
		"""The session such an object was created in."""
		return self._session

	def result(self, index):
		"""Return an object representation for the object at this index of results."""
		if isinstance(index, slice):
			# Return plural type for slice
			number = Number.PLURAL
		else:
			# Not a slice -> convert to slice for simplification
			index = slice(index, index + 1)
			# Return singular type
			number = Number.SINGULAR

		# Get results of the objects in this slice
		results = [super().result(i) for i in range(len(self))[index]]
		# Get names of the objects in this slice
		names = [res["name"] for res in results]
		# Construct a filter for these names
		# TODO check how that works for objects with composite names (e.g. services)
		filterstring = "{}.name==\"{}\"".format(self.type, "\" || {}.name==\"".format(self.type).join(names))

		# Copy query for these objects
		req = self._request.clone()
		req.json = dict(req.json)
		# Apply constructed filter and return the result of this query
		req.json["filter"] = filterstring
		class_ = self._session.types.type(self.type, number)
		# TODO check whether that works, I'm not sure
		return class_(self._session, req, results=results, next_cache_expiry=self._expires)

	@property
	def type(self):
		"""The type of this/these object(s). Always returns the singular name."""
		return self.DESC["name"]

	def parse_attrs(self, attrs):
		"""Parse attrs string.
		"attrs.state" -> ["attrs", "state"]
		"name" -> ["name"]
		"last_check_result.output" -> ["attrs", "last_check_result", "output"]

		Also on a <Type, e.g. host> object:
		"<typename>.last_check_result.output" -> ["attrs", "last_check_result", "output"]

		Also on a <Type> that is in the list of joins (looked up in the request):
		"<typename>.last_check_result.output" -> ["joins", <typename>, "last_check_result", "output"]
		"""
		split = attrs.split('.')

		# First key (name, type, attrs, joins, meta) - defaults to attrs
		if split[0] not in OBJECT_QUERY_RESULT_KEYS:
			# First key of attrs is not one that is handled "naturally"
			if split[0].lower() == self.type.lower():
				# Key is own type; cut first entry of split and insert "attrs" instead
				return ["attrs"] + split[1:]
			elif split[0] in self._request.json.get("joins", tuple()):
				# Type in joins
				return ["joins"] + split
			else:
				# Default is to insert "attrs" at the start
				return ["attrs"] + split
		# else
		return split

	def permissions(self, attr):
		"""Get permission for a given attribute (field), returned as a tuple for the boolean values of:
		no_user_view, no_user_modify
		All values True is the default."""
		try:
			field = self.FIELDS[attr]["attributes"]
		except KeyError:
			return True, True
		return field.get("no_user_view", True), field.get("no_user_modify", True)

	def _attribute_type(self, attr):
		"""Return type class for an attribute given by name."""
		typename = self.FIEDLS[attr]["type"]
		return self._session.types.type(typename)

	def __setattr__(self, key, value):
		"""Modify object value(s) if the attribute name is a field of this object type. Otherwise default behavior."""
		if (key and key[0] == '_') or (self.parse_attrs(key)[1] not in self.FIELDS):
			# Fallback to default for non-fields
			return super().__setattr__(key, value)

		# Modify this object
		# TODO use attr somehow and avoid parse_attrs for a second time this way
		self.modify({key: value})

	def modify(self, modification):
		"""Modify this/these objects. Attributes and their new values as a dict.
		This method checks if modification is allowed, converts the values and sends the modification to Icinga.
		If Icinga returns a HTTP status_code<400 attribute values are also written to the objects results cache.
		# TODO later: setting attributes should be separate from Icinga modification request
		"""

		# What is later send as an Icinga request
		change = {}
		for oldkey, oldval in modification.items():
			attr = self.parse_attrs(oldkey)
			if attr[0] == "joins":
				raise NoUserModify("Modification of a joined object is not supported.")
			elif attr[0] != "attrs":
				raise NoUserModify("Not allowed to modify attribute {}. Not an attribute.".format(key))

			key = ".".join(attr)

			# Check if modification is allowed
			if self.permissions(attr)[1]:
				raise NoUserModify("Not allowed to modify attribute {}".format(key))

			# Convert attribute value type
			type_ = self._attribute_type(attr[1])
			# TODO treat ObjectAttribute values
			# TODO check number=irrelevant is ok here for the type
			change[key] = type_.convert(self, key, oldval)

		# Create modification query
		mquery = self._request.clone()
		mquery.method_override = "POST"
		# Copy original JSON body and overwrite attributes for modification
		data = dict(mquery.json)["attrs"] = {}
		data["attrs"] = change
		# JSON Encoding
		mquery.data = json.dumps(data, cls=JSONResultEncoder)
		# Not neccessary, but avoids confusion
		del mquery.json
		# Fire modification query (returns APIResponse object)
		ret = mquery()

		if ret.status_code >= 400:
			# Something went wrong -> do not modify
			return ret

		# Modify cached attribute values
		for res in self.results:
			for key, value in change.items():
				res[self.parse_attrs(key)] = value

		return ret


class IcingaConfigObject(IcingaObject, IcingaConfigObjects):
	"""Representation of an Icinga object."""

	# The DESC is overriden in subclasses with the Icinga type description
	DESC = {}
	# The FIELDS is override in subclasses with all FIELDS and their description for the object type (incl. from parents)
	FIELDS = {}

	def __init__(self, session, request, response=None, results=None, next_cache_expiry=None):
		# Call other super init first
		IcingaConfigObjects.__init__(self, session, request, response, results, next_cache_expiry)
		# Call super init of Result, overwrites results
		super().__init__(results)

	@property
	def name(self):
		"""The name of this object."""
		return self["name"]

	def __getitem__(self, item):
		"""Implements sequence and mapping access in one."""
		if isinstance(item, (int, slice)):
			super().__getitem__(item)

		# Mapping access
		attr = self.parse_attrs(item)
		if attr[0] == "attrs":
			# Check no_user_view
			if self.permissions(attr[1])[0]:
				raise NoUserView("Not allowed to view attribute {}".format(attr))
		# Dictionaries and such stuff are handled because the use of the customized JSONDecoder
		return super().__getitem__(attr)

	def __getattr__(self, attr):
		"""Get value of a field."""
		attr = self.parse_attrs(attr)
		if attr[0] == "attrs" and attr[1] not in self.FIELDS:
			raise AttributeError

		# Mapping access - let __getitem__ do the real work
		return self[attr]
