# -*- coding: utf-8 -*-
"""
This module defines simple mapped object types, especially object types natively included in Python.

There is also a JSON Encoder in this module, that is able to encode all AttributeValue objects.
Below the encoder is a JSON decoder helper, that provides a object_pairs_hook method for decoding.
# TODO move the JSON things to a different module, they don't fit here anymore
"""

from json import JSONEncoder
import datetime
import functools
import collections.abc

from .base import Number, ParentObjectDescription, AbstractIcingaObject
from ..results import Result


class NativeValue(AbstractIcingaObject):
	"""Base class for all type classes that describe a type as-is (simple native Python object like e.g. int)."""

	def __init__(self, value, parent_descr):
		super().__init__(parent_descr=parent_descr)
		self._value = value

	@property
	def value(self):
		return self._value

	@classmethod
	def convert(cls, obj, parent_descr):
		return cls(cls.converter(obj), parent_descr)

	def __str__(self):
		return str(self._value)

	@classmethod
	def converter(cls, x):
		"""Convert Python object to Icinga value, default does just return the object."""
		return x


def create_native_attribute_value_type(name, converter=None):
	"""Create a simple NativeAttributeValue subclass using a converter."""
	if converter:
		return type(name, (NativeValue, ), {"converter": converter, "__module__": NativeValue.__module__})
	else:
		return type(name, (NativeValue, ), {"__module__": NativeValue.__module__})


class TimestampMeta(type):
	"""Metaclass for Timestamp."""
	def __new__(mcs, name, parents, namespace):
		cls = super().__new__(mcs, name, parents, namespace)
		# Add properties for everything in "DATETIME_PROPERTIES"
		for attr in cls.DATETIME_PROPERTIES:
			setattr(cls, attr, property(functools.partialmethod(cls.get_property, attr)))
		return cls


class Timestamp(AbstractIcingaObject, metaclass=TimestampMeta):
	"""Icinga timestamp type.

	A timestamp as a float on the Icinga side.
	Here Timestamp is usable both as datetime.datetime as well as float (timestamp).
	"""

	# TODO make Timetsamp working
	# TODO add missing datetime properties

	DATETIME_PROPERTIES = ("hour", "minute", "second")

	def __init__(self, value, parent_descr):
		super().__init__(value, parent_descr)
		self._dt = datetime.datetime.utcfromtimestamp(value)

	@property
	def datetime(self):
		"""Return a appropriate datetime.datetime object."""
		return self._dt

	def get_property(self, property):
		"""Get a property of datetime."""
		return getattr(self.datetime, property)


class Duration(AbstractIcingaObject):
	"""Icinga duration attribute type. A string on Icinga side, union of string and float here."""
	# TODO implement


class Array(NativeValue, collections.abc.Sequence):
	"""Icinga Array attribute type. A sequence here."""
	# TODO MutableSequence

	def __init__(self, value, parent_descr):
		super().__init__(value, parent_descr)

	@classmethod
	def converter(cls, x):
		return list(x)

	def __getitem__(self, item):
		return self._value.__getitem__(item)

	def __len__(self):
		return self._value.__len__()


class Dictionary(NativeValue, collections.abc.Mapping):
	"""Icinga Dictionary attribute type. Also something like a dictionary here."""
	# TODO MutableMapping

	def __init__(self, value, parent_descr):
		super().__init__(value, parent_descr)

	@classmethod
	def converter(cls, x):
		return dict(x)

	# TODO - this is bad (design)
	parse_attrs = Result.parse_attrs

	def __getitem__(self, item):
		"""Mapping access with dot-syntax."""
		try:
			ret = self._value
			for item in self.parse_attrs(item):
				ret = ret[item]
			return ret
		except (KeyError, ValueError):
			raise KeyError("No such key: {}".format(item))

	def __len__(self):
		return self._value.__len__()

	def __iter__(self):
		return self._value.__iter__()


class JSONResultEncoder(JSONEncoder):
	"""Encode Python representation of result(s) to JSON."""

	def default(self, o):
		if isinstance(o, NativeValue):
			# Just serialize the value
			return super().default(o.value)
		super().default(o)


class JSONResultDecodeHelper:
	"""Helper for decoding JSON encoded results. Provides a object_pairs_hook."""

	def __init__(self, parent_object):
		self._parent_object = parent_object

	def object_pairs_hook(self, pairs):
		"""The object_pairs_hook for JSON-decoding."""
		res = {}
		for key, value in pairs:
			if key == "results":
				# Final conversion for everything else than list and dict depending on the parent_object's fields
				value = self.final_conversion(value)
			res[key] = value
		return res

	def final_conversion(self, objects):
		"""Final type conversion for passed objects. The conversion depends on the parent_object's fields and their
		types."""
		# Return value
		ret = []
		# Iterate over objects
		for obj in objects:
			# New object
			res = {}
			for key, value in obj.get("attrs", dict()).items():
				try:
					type_ = self._parent_object.FIELDS[key]["type"]
					type_ = self._parent_object.session.types.type(type_, Number.SINGULAR)
				except KeyError:
					type_ = None
				if type_:
					# Type needs to be an AbtractIcingaObject for this to work
					parent_descr = ParentObjectDescription(parent=self._parent_object, field=key)
					res[key] = type_.convert(value, parent_descr)
				else:
					# No type conversion at all, because explicitely suppressed or type is not supported
					res[key] = value

			ret.append(res)

		return ret
