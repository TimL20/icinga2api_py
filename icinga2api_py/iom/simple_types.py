# -*- coding: utf-8 -*-
"""
This module defines simple mapped object types, especially object types natively included in Python.

There is also a JSON Encoder in this module, that is able to encode all AttributeValue objects.
Below the encoder is a JSON decoder helper, that provides a object_pairs_hook method for decoding.
"""

import datetime
import collections.abc


from .base import Number, ParentObjectDescription, AbstractIcingaObject
from .exceptions import NoUserModify
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


# TODO add simple native types to make them importable


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


class Dictionary(NativeValue, collections.abc.MutableMapping):
	"""Icinga Dictionary attribute type. Also something like a dictionary here."""

	# TODO implement nested dictionaries

	def __init__(self, value, parent_descr):
		# Icinga may return (JSON) null (=Python None) for an empty dict (e.g. empty vars)
		value = value if value is not None else dict()
		super().__init__(value, parent_descr)

	@classmethod
	def converter(cls, x):
		# Icinga may return (JSON) null (=Python None) for an empty dict (e.g. empty vars)
		x = x if x is not None else dict()
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

	def modify(self, modification):
		"""Modify this dictionary."""
		# Let the parent object handle modification if there is one
		if self.parent_descr.parent is not None:
			# Parse all attrs and prefix with field
			modification = {(self.parent_descr.field, *self.parse_attrs(key)): val for key, val in modification.items()}
			# Propagate modification to let the parent handle it
			return self.parent_descr.parent.modify(modification)

		for key, value in modification.items():
			temp = self._value
			attrs = self.parse_attrs(key)
			for subkey in attrs[:-1]:
				temp = temp.setdefault(subkey, dict())
			temp[attrs[-1]] = value

	def __setitem__(self, item, value):
		"""Set a value of a specific item."""
		self.modify({item: value})

	def __delitem__(self, item):
		"""Delete an item."""
		raise NoUserModify("Deleting an item is not supported (yet)")  # TODO implement

	def __len__(self):
		return self._value.__len__()

	def __iter__(self):
		return self._value.__iter__()

	def __getattr__(self, item):
		"""Get a value, basically lets __getitem__ do the work"""
		try:
			return self.__getitem__(item)
		except KeyError:
			raise AttributeError(f"Unable to find value for {item}")

	def __setattr__(self, item, value):
		"""Set a value with __setitem__ unless handled."""
		if item[0] == "_":
			return super().__setattr__(item, value)
		return self.__setitem__(item, value)

	def __delattr__(self, item):
		"""Delete an item with __delitem__."""
		return self.__delitem__(item)
