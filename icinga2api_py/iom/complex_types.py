# -*- coding: utf-8 -*-
"""This module defines complex mapped object types.

The classes for the mapped Icinga objects are created in the types module, but most classes created there inherit from
a class here.
No thread-safety (yet).
"""

import json

from .exceptions import NoUserView, NoUserModify
from ..results import ResultSet, CachedResultSet, SingleResultMixin
from .base import Number, AbstractIcingaObject, ParentObjectDescription
from .simple_types import JSONResultEncoder, JSONResultDecodeHelper

# Possible keys of an objects query result
OBJECT_QUERY_RESULT_KEYS = {"name", "type", "attrs", "joins", "meta"}


class IcingaObjects(AbstractIcingaObject, ResultSet):
	"""Base class of every representation of any number of Icinga objects that have the same type."""

	def result(self, index):
		"""Return an appropriate IcingaObject or (in case of a slice) IcingaObjects object."""
		if isinstance(index, slice):
			return IcingaObjects(self.results[index], parent_descr=self.parent_descr)
		return IcingaObject((self.results[index],), parent_descr=self.parent_descr)

	@classmethod
	def convert(cls, obj, parent_descr):
		# The object is handled as a sequence of mappings to convert it
		try:
			results = [dict(item) for item in obj]
			# Create with results and parent_descr
			return cls(results, parent_descr=parent_descr)
		except (TypeError, IndexError, KeyError):
			raise TypeError(f"{obj.__class__.__name__} could not be converted to a {cls.__name__} object")


class SingleObjectMixin(SingleResultMixin):
	"""Extending SingleResultMixin with better field access."""

	def __getitem__(self, item):
		"""Implements sequence and mapping access in one."""
		if isinstance(item, (int, slice)):
			return super().__getitem__(item)

		# Mapping access
		attr = self.parse_attrs(item)
		if attr[0] == "attrs":
			# Check no_user_view
			if self.permissions(attr[1])[0]:
				raise NoUserView("Not allowed to view attribute {}".format(attr))

		obj = super().__getitem__(attr)
		try:
			# Return value property if possible, useful for native types
			return obj.value
		except AttributeError:
			return obj

	def __getattr__(self, attr):
		"""Get value of a field."""
		attr = self.parse_attrs(attr)
		if attr[0] == "attrs" and attr[1] not in self.FIELDS:
			raise AttributeError

		# Mapping access - let __getitem__ do the real work
		try:
			return self[attr]
		except KeyError:
			raise AttributeError


class IcingaObject(SingleObjectMixin, IcingaObjects):
	"""Representation of exactly one Icinga object."""

	@classmethod
	def convert(cls, obj, parent_descr):
		# Convert obj to a sequence with that one item and let the plural type class handle that
		return super().convert((obj, ), parent_descr)


class IcingaConfigObjects(CachedResultSet, IcingaObjects):
	"""Representation of any number of Icinga objects that have the same type.
	This is the parent class of all dynamically created Icinga configuration object type classes."""

	def __init__(self, results=None, response=None, request=None, cache_time=float("inf"), next_cache_expiry=None,
				parent_descr=None, json_kwargs=None):
		super().__init__(results, response, request, cache_time, next_cache_expiry, json_kwargs)
		IcingaObjects.__init__(self, results, parent_descr=parent_descr)

		# JSON Decoding
		self._json_kwargs["object_pairs_hook"] = JSONResultDecodeHelper(self).object_pairs_hook

	def result(self, index):
		"""Return an object representation for the object at this index of results."""
		# Hold cache while doing this
		with self:
			return self._result0(index)

	def _result0(self, index):
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
		# super() does not work in list comprehensions
		super_ = super()
		results = [super_.result(i) for i in range(len(self))[index]]

		# Get names of the objects in this slice
		names = [res["name"] for res in results]
		# Construct a filter for these names
		# TODO make this work for objects with composite names (e.g. services)
		filterstring = "{}.name==\"{}\"".format(
			self.type.lower(),
			"\" || {}.name==\"".format(self.type.lower()).join(names)
		)

		# Copy query for these objects
		req = self.request.clone()
		req.json = dict(req.json)
		# Apply constructed filter and return the result of this query
		req.json["filter"] = filterstring
		class_ = self.session.types.type(self.type, number)
		return class_(
			self.results[index],
			request=req,  # Request to load this single object
			cache_time=self.cache_time, next_cache_expiry=self._expires,  # "Inherit" cache time and next expiry
			parent_descr=self.parent_descr
		)

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
		split = super().parse_attrs(attrs)

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

	def __setattr__(self, key, value):
		"""Modify object value(s) if the attribute name is a field of this object type. Otherwise default behavior."""
		# Short circuiting is essential here, because parse_attrs may fail when the object is not fully initialized yet
		if (key and key[0] == '_') or (self.parse_attrs(key)[1] not in self.FIELDS):
			# Fallback to default for non-fields
			return super().__setattr__(key, value)

		# Modify this object
		# With Python 3.8 a walrus operator could be used to avoid parse_attrs a second time...
		# Can't be used above, because short-circuiting is essential there
		self.modify({key: value})

	def modify(self, modification):
		"""Modify this/these objects.

		Takes attributes and their new values as a dict.
		This method checks if modification is allowed, converts the values and sends the modification to Icinga.
		If Icinga returns a HTTP status_code<400 attribute values are also written to the objects results cache.
		"""

		# What is later send as an Icinga request
		change = {}
		for oldkey, oldval in modification.items():
			attr = self.parse_attrs(oldkey)
			key = ".".join(attr)

			# Check if modification is allowed
			if attr[0] == "joins":
				raise NoUserModify("Modification of a joined object is not supported.")
			elif attr[0] != "attrs":
				raise NoUserModify("Not allowed to modify attribute {}. Not an attribute.".format(key))

			if self.permissions(attr[1])[1]:
				raise NoUserModify("No permission to modify attribute {}".format(key))

			# Convert attribute value type
			type_ = self._field_type(attr[1])
			change[key] = type_.convert(oldval, parent_descr=ParentObjectDescription(parent=self, field=key))

		ret = self._modify0(change)

		if ret.status_code >= 400:
			# Something went wrong -> do not modify
			return ret

		# Modify cached attribute values
		for res in self.results:
			for key, value in change.items():
				key = self.parse_attrs(key)[1]
				res[key] = value

		return ret

	def _modify0(self, modification):
		"""Actually apply a modification with correctly converted values."""
		# Create modification query
		mquery = self._request.clone()
		mquery.method_override = "POST"
		# Copy original JSON body and overwrite attributes for modification
		data = dict(mquery.json)["attrs"] = {}
		data["attrs"] = modification
		# JSON Encoding
		mquery.data = json.dumps(data, cls=JSONResultEncoder)
		# Should not be neccessary because requests uses data first, but avoids confusion
		mquery.json = dict()
		# Fire modification query (returns APIResponse object)
		return mquery()


class IcingaConfigObject(SingleObjectMixin, IcingaConfigObjects):
	"""Representation of an Icinga object."""
