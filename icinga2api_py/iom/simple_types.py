# -*- coding: utf-8 -*-
"""
This module defines simple mapped object types, especially object types natively included in Python.

There is also a JSON Encoder in this module, that is able to encode all AttributeValue objects.
Below the encoder is a JSON decoder helper, that provides a object_pairs_hook method for decoding.
# TODO move the JSON things to a different module, they don't fit here anymore
"""

from json import JSONEncoder
import datetime
import collections.abc

from .base import Number, ParentObjectDescription, AbstractIcingaObject
from ..results import ResultSet


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

	def __eq__(self, other):
		return self.value == other

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


class Timestamp(NativeValue):
	"""Icinga timestamp type.

	A timestamp as a float on the Icinga side.
	Here Timestamp is usable both as datetime.datetime as well as float (seconds since epoch).
	"""

	#: Datetime attributes made available via __getattr__
	DATETIME_ATTRIBUTES = {
		"year", "month", "day", "toordinal", "weekday", "isoweekday", "isocalendar",
		"hour", "minute", "second", "microsecond", "fold", "tzinfo", "utcoffset", "dst",
		"timetuple", "timestamp", "date", "time",
		"ctime", "isoformat", "strftime", "tzname",
	}

	def __init__(self, value, parent_descr):
		super().__init__(value, parent_descr)
		self._datetime = None

	@property
	def datetime(self):
		"""Return an appropriate datetime.datetime object."""
		if self._datetime is None:
			self._datetime = datetime.datetime.fromtimestamp(self.value, datetime.timezone.utc)
		return self._datetime

	def __getattr__(self, item):
		"""Try to get an attribute of the datetime object."""
		if item in self.DATETIME_ATTRIBUTES:
			return getattr(self.datetime, item)
		raise AttributeError(f"No such attribute: {item}")

	# TODO implement timestamp manipulation

	# TODO implement timestamp and float/int comparison

	@classmethod
	def converter(cls, x):
		if isinstance(x, datetime.datetime):
			return x.timestamp()
		else:
			# Handle as timestamp (seconds since epoch)
			return float(x)


class Duration(AbstractIcingaObject):
	"""Icinga duration attribute type. A string on Icinga side, union of string and float here."""
	# TODO implement


class Array(NativeValue, collections.abc.Sequence):
	"""Icinga Array attribute type. A sequence here."""
	# TODO MutableSequence

	def __init__(self, value, parent_descr):
		super().__init__(list(value), parent_descr)

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

	@staticmethod
	def parse_attrs(attrs):
		"""Parse attrs with :meth:`icinga2api_py.results.ResultSet.parse_attrs`."""
		return ResultSet.parse_attrs(attrs)

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
		try:
			# Just serialize the value, works with NativeValue
			return o.value
		except AttributeError:
			pass
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
			res = {"attrs": {}}
			for key, value in obj.get("attrs", dict()).items():
				try:
					type_ = self._parent_object.FIELDS[key]["type"]
					type_ = self._parent_object.session.types.type(type_, Number.SINGULAR)
				except KeyError:
					type_ = None
				if type_:
					# Type needs to be an AbtractIcingaObject for this to work
					parent_descr = ParentObjectDescription(parent=self._parent_object, field=key)
					res["attrs"][key] = type_.convert(value, parent_descr)
				else:
					# No type conversion at all, because explicitely suppressed or type is not supported
					res["attrs"][key] = value

			obj.update(res)
			ret.append(obj)

		return ret
