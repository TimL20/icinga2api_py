# -*- coding: utf-8 -*-
"""This module defines attribute value types.
As IcingaObjects can also be attribute values (as reference e.g. ´host_name´ in Service
or directly e.g. ´last_check_result´ in Checkable) this is also linked to the objects module...

There is also a JSON Encoder in this module, that is able to encode all AttributeValue objects.
Below the encoder is a JSON decoder helper, that provides a object_pairs_hook method for decoding."""

from json import JSONEncoder
import datetime
import functools
import collections.abc
from .base import Number
from ..results import Result


class AttributeValue:
	"""Base class for all attribute value types.
	The tasks are the following conversions:
	- Icinga value to Python object
	- Python object of this class to Icinga value
	- Other Python object to Python object of this class (convert)"""
	def __init__(self, parent_object, attribute, value):
		"""Init attribute value object with
		:param parent_object: the object of which this is an attribute value
		:param attribute: the attribute name (senn from the parent_object)
		:param value: The attribute value as delivered from Icinga
		"""
		self._parent_object = parent_object
		self._attribute = attribute
		self._value = value

	@classmethod
	def convert(cls, parent_object, key, value):
		"""Convert other Python object to an object of this class if possible."""
		return cls(parent_object, key, value)

	@classmethod
	def direct_convert(cls, parent_object, key, value):
		"""Convert other Python object to Icinga value that would also result from ´cls.convert(value).value()´.
		The default implementation is a fallback for subclasses."""
		return cls.convert(parent_object, key, value).value()

	def value(self):
		"""Get value for Icinga."""
		return self._value

	def __str__(self):
		return str(self._value)


class NativeAttributeValue(AttributeValue):
	"""For attribute value types that are native (builtin) Python types.
	Basically just implements type conversion and requires the converter to do all the work or raise errors.
	The default implementation does nothing, but overriding the converter (in subclasses) makes it useful."""

	@classmethod
	def converter(cls, x):
		"""Convert Python object to Icinga value. Default does just return the object."""
		return x

	@classmethod
	def convert(cls, parent_object, key, value):
		"""Other Python object to an object ot this class."""
		return super().convert(parent_object, key, cls.converter(value))

	@classmethod
	def direct_convert(cls, parent_object, key, value):
		"""Python object to Icinga value."""
		return cls.converter(value)


def create_native_attribute_value_type(name, converter=None):
	"""Create a NativeAttributeValue class using a converter."""
	if converter:
		return type(name, (AttributeValue, ), {"converter": converter, "__module__": AttributeValue.__module__})
	else:
		return type(name, (AttributeValue, ), {"__module__": AttributeValue.__module__})


class TimestampMeta(type):
	"""Metaclass for Timestamp."""
	def __new__(mcs, name, parents, namespace):
		cls = super().__new__(mcs, name, parents, namespace)
		# Add properties for everything in "DATETIME_PROPERTIES"
		for attr in cls.DATETIME_PROPERTIES:
			setattr(cls, attr, property(functools.partialmethod(cls.get_property, attr)))
		return cls


class Timestamp(AttributeValue, metaclass=TimestampMeta):
	"""Icinga timestamp attribute type. A timestamp as a float on the Icinga side.
	Here Timestamp is usable both as datetime.datetime as well as float (timestamp)."""
	# TODO make Timetsamp working
	# TODO add missing datetime properties
	DATETIME_PROPERTIES = ("hour", "minute", "second")

	def __init__(self, parent_object, attribute, value):
		super().__init__(parent_object, attribute, value)
		self._dt = datetime.datetime.utcfromtimestamp(value)

	@property
	def datetime(self):
		"""Return a appropriate datetime.datetime object."""
		return self._dt

	def get_property(self, property):
		"""Get a property of datetime."""
		return getattr(self.datetime, property)


class Duration(AttributeValue):
	"""Icinga duration attribute type. A string on Icinga side, union of string and float here."""
	# TODO implement


class Array(AttributeValue, collections.abc.Sequence):
	"""Icinga Array attribute type. A sequence here."""
	# TODO MutableSequence
	def __init__(self, parent_object, attribute, value):
		super().__init__(parent_object, attribute, value)

	@classmethod
	def direct_convert(cls, parent_object, key, value):
		return value

	def __getitem__(self, item):
		return self._value.__getitem__(item)

	def __len__(self):
		return self._value.__len__()


class Dictionary(AttributeValue, collections.abc.Mapping):
	"""Icinga Dictionary attribute type. Also something like a dictionary here."""
	# TODO MutableMapping
	def __init__(self, parent_object, attribute, value):
		super().__init__(parent_object, attribute, value)

	@classmethod
	def direct_convert(cls, parent_object, key, value):
		return value

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
		if isinstance(o, AttributeValue):
			# Just serialize the value
			return super().default(o.value())
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
					# This fails evertime type_ is not an AttributeValue, e.g. if it's a IcingaConfigObjects
					# TODO make this somehow work everytime...
					res[key] = type_(self._parent_object, key, value)
				else:
					# No type conversion at all, because explicitely suppressed or type is not supported
					res[key] = value

			ret.append(res)

		return ret
