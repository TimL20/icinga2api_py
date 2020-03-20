# -*- coding: utf-8 -*-
"""This module defines complex mapped object types.

The classes for the mapped Icinga objects are created in the types module, but most classes created there inherit from
a class here.
No thread-safety (yet).
"""

import collections.abc
import time
import typing

from requests import HTTPError

from icinga2api_py.models import APIResponse
from .exceptions import NoUserView, NoUserModify
from ..results import ResultSet, CachedResultSet, SingleResultMixin
from .base import TypeNumber, AbstractIcingaObject, ParentObjectDescription

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

	def field_value_object(self, field, value):
		"""Get an object for the given field with the given value."""
		# Check no_user_view
		if self.permissions(field)[0]:
			raise NoUserView(f"Not allowed to view field {field}")

		try:
			type_ = self._field_type(field)
		except KeyError:
			type_ = None
		if type_:
			# Type is assumed to be an AbstractIcingaObject
			parent_descr = ParentObjectDescription(parent=self, field=field)
			return type_.convert(value, parent_descr)
		else:
			# No type conversion at all, because explicitely suppressed or type is not supported
			return value


_SingleObjectType = typing.Union["SingleObjectMixin", IcingaObjects]


class SingleObjectMixin(SingleResultMixin):
	"""Extending SingleResultMixin with better field access."""

	def field_object(self: _SingleObjectType, field):
		"""Get an object for the value of the given field."""
		value = self._raw["attrs"][field]
		return self.field_value_object(field, value)

	def __getitem__(self: _SingleObjectType, item):
		"""Implements sequence and mapping access in one."""
		if isinstance(item, (int, slice)):
			return super().__getitem__(item)

		# Mapping access
		attr = self.parse_attrs(item)
		if attr[0] == "attrs" and len(attr) > 1:
			obj = self.field_object(attr[1])
			return self.attr_value(attr[2:], obj)
		else:
			return super().__getitem__(attr)

	def __getattr__(self: _SingleObjectType, attr):
		"""Get value of a field."""
		attr = self.parse_attrs(attr)
		if attr[0] == "attrs" and attr[1] not in self.FIELDS:
			raise AttributeError

		# Mapping access - let __getitem__ do the real work
		try:
			return self[attr]
		except KeyError:
			raise AttributeError


class IcingaObject(SingleObjectMixin, IcingaObjects, collections.abc.Mapping):
	"""Representation of exactly one Icinga object."""

	@classmethod
	def convert(cls, obj, parent_descr):
		# Convert obj to a sequence with that one item and let the plural type class handle that
		return super().convert((obj, ), parent_descr)


class IcingaConfigObjects(CachedResultSet, IcingaObjects):
	"""Representation of any number of Icinga objects that have the same type.
	This is the parent class of all dynamically created Icinga configuration object type classes."""

	def __init__(self, results=None, response=None, request=None, cache_time=float("inf"), next_cache_expiry=None,
				parent_descr=None, timefunc=time.time, json_kwargs=None):
		super().__init__(results, response, request, cache_time, next_cache_expiry, timefunc, json_kwargs=json_kwargs)
		IcingaObjects.__init__(self, results, parent_descr=parent_descr)

	def result(self, index):
		"""Return an object representation for the object at this index of results."""
		# Hold cache while doing this
		with self:
			return self._result0(index)

	def _result0(self, index):
		"""Return an object representation for the object at this index of results."""
		if isinstance(index, slice):
			# Return plural type for slice
			number = TypeNumber.PLURAL
		else:
			# Not a slice -> convert to slice for simplification
			index = slice(index, index + 1)
			# Return singular type
			number = TypeNumber.SINGULAR

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
		split = list(super().parse_attrs(attrs))

		# First key (name, type, attrs, joins, meta) - defaults to attrs
		# TODO make the lookups safe (maybe put lookups into other methods?)
		# TODO what is with attrs restriction in the request? That doesn't work...
		if split[0] not in OBJECT_QUERY_RESULT_KEYS:
			# First key of attrs is not one that is handled "naturally"
			if split[0].lower() == self.type.lower():
				# Key is own type; cut first entry of split and insert "attrs" instead
				return ["attrs"] + split[1:]
			elif split[0] in self._request.json.get("joins", tuple()):
				# Type in joins
				# TODO this will not work with joined attributes
				return ["joins"] + split
			else:
				# Default is to insert "attrs" at the start
				return ["attrs"] + split
		# else
		return split

	def _modify_prepare(self, modification) -> typing.Mapping:
		"""Prepare modification: Unify the modification mapping.

		After this step, the returned modification mapping has the form <field> -> <Object of the field's type>,
		or <field> -> <subfield> -> ... -> <value> (in case of sub-fields)
		- no matter how it has been before (unless invalid or not allowed).

		:raises NoUserModify: When modification is not allowed for whatever reason.
		:raises KeyError: When something else is odd.
		"""
		change = dict()
		for oldkey, oldvalue in modification.items():
			attr = self.parse_attrs(oldkey)
			key = ".".join(attr)

			# Check if modification is allowed
			if attr[0] == "joins":
				raise NoUserModify("Modification of a joined object is not supported.")
			elif attr[0] != "attrs" or len(attr) <= 1:
				raise NoUserModify("Not allowed to modify attribute {}. Not an attribute.".format(key))

			if self.permissions(attr[1])[1]:
				raise NoUserModify("No permission to modify attribute {}".format(key))

			if len(attr) == 2:
				# Modify whole field
				change[attr[1]] = self.field_value_object(attr[1], oldvalue)
			else:
				# Modify subfield
				# Create empty type of the field, which supports subfields
				fobj = self.field_value_object(attr[1], None)
				# Decouple field object from its parent (this IcingaConfigObject)
				# This way it does handle modification itself rather than propagating it (which whould led to recursion)
				fobj.parent_descr.decouple()
				fobj[tuple(attr[2:])] = oldvalue

				# Use the part of fobj that was "changed" for the returned changes, use a string-key
				change[".".join(attr[1:])] = fobj[attr[2:]]

		return change

	def modify(self, modification):
		"""Modify this/these objects.

		Takes attributes and their new values as a dict.
		This method checks if modification is allowed, converts the values and sends the modification to Icinga.
		If Icinga returns a HTTP status_code<400 attribute values are also written to the objects results cache.
		"""
		modification = self._modify_prepare(modification)
		# TODO guarantee that values get converted correctly...
		# This is only guaranteed to work for NativeValue objects
		modification = {key: getattr(value, "value", value) for key, value in modification.items()}

		ret = self._modify_icinga(modification)
		try:
			ret.raise_for_status()
		except HTTPError:
			pass  # Not successfull -> do not modify
		else:
			# Modify cached attribute values
			self._modify_internal(modification)
		return ret

	def _modify_internal(self, modification):
		"""Modify the internal (cached) attribute values ("attrs" field only)."""
		for res in self.results:
			for key, value in modification.items():
				# The following part is neccesary to support partial changes of e.g. dictionaries
				temp = res["attrs"]
				attrs = self.parse_attrs(key)
				for subkey in attrs[1:-1]:
					if temp[subkey] is None:
						# Unfortunately, for Icinga a Dictionary can be Null/None
						# As to this point Icinga has accepted the change, None must therefore be a dictionary
						temp[subkey] = dict()
					temp = temp.setdefault(subkey, dict())
				temp[attrs[-1]] = value

	def _modify_icinga(self, modification) -> APIResponse:
		"""Send a modification request to Icinga and return the response."""
		# Create modification query
		mquery = self._request.clone()
		mquery.method_override = "POST"
		# Copy original JSON body and overwrite attributes for modification
		data = dict(mquery.json)["attrs"] = {}
		data["attrs"] = modification
		mquery.json = data
		# Fire modification query (returns APIResponse object)
		return mquery()


class IcingaConfigObject(SingleObjectMixin, IcingaConfigObjects):
	"""Representation of an Icinga object."""

	def __setattr__(self, key, value):
		"""Modify object value(s) if the attribute name is a field of this object type. Otherwise default behavior."""
		if key and key[0] == '_':
			# Default behavior for private attributes
			return super().__setattr__(key, value)

		attrs = self.parse_attrs(key)
		if len(attrs) > 1 and attrs[1] not in self.FIELDS:
			# Fallback to default for non-fields
			return super().__setattr__(key, value)

		# Modify this object
		self.modify({tuple(attrs): value})
