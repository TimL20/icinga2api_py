# -*- coding: utf-8 -*-
"""
This module defines simple mapped object types, especially object types natively included in Python.
"""

import datetime
from collections.abc import Sequence, Mapping, MutableMapping


from .base import ParentObjectDescription, AbstractIcingaObject
from .exceptions import NoUserModify
from ..results import ResultSet


__all__ = ["Number", "String", "Boolean", "Value", "Timestamp", "Duration", "Array", "Dictionary"]


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

	def __repr__(self):
		return f"<{self.__class__.__name__}: {repr(self._value)}>"

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


#: Type for any Number, wraps a Python ´float´
Number = create_native_attribute_value_type("Number", float)
#: Type for any String, wraps a Python ´str´
String = create_native_attribute_value_type("String", str)
#: Type for any Boolean, wraps a Python ´bool´
Boolean = create_native_attribute_value_type("Boolean", bool)

# This is actually something a bit odd, and reading the Icinga2 documentation doesn't help much here
# It's not mentioned in "Monitoring Basics" -> "Attribute Value types"
# Nor in "Advanced Topics" -> "Advanced Value Types"
# And also not in "Object Types" or "Api"
# But it appears in the query result of API /types endpoint, in:
# Checkable -> check_timeout, Command -> {arguments, command}, PerfdataValue -> {min, max, warn},
# ScheduledDowntime -> child_options, TimePeriod -> {valid_begin, valid_end}
# Not sure how to handle this -> just leave it like it is  # TODO question or issue for Icinga ???
#: For now this is just a "leave it untouched" type
Value = create_native_attribute_value_type("Value")


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


class _NativeContainerMixin:
	"""Base type for containers.

	This is basically a collections of utility functions both Dictionary and Array use.
	"""

	def _convert_container(self, key, value):
		"""If value is a container, convert it to an appropriate type (Dictionary or Array)."""
		# This isinstance checks are fine as long as value is created by the default JSON parser
		if isinstance(value, list):
			return Array(value, ParentObjectDescription(parent=self, field=key))
		elif isinstance(value, Mapping):
			return Dictionary(value, ParentObjectDescription(parent=self, field=key))
		return value

	@classmethod
	def _ensure_mapping_string_keys(cls, mapping: Mapping):
		"""Recursively ensure that every key of the mapping is a string (because Icinga only knows strings as keys).

		To make things easy, this will actually create a new dictionary.
		"""
		ret = dict()
		for key, value in mapping.items():
			if isinstance(value, Mapping):
				ret[str(key)] = cls._ensure_mapping_string_keys(value)
			elif isinstance(value, Sequence):
				ret[str(key)] = cls._ensure_sequence_string_keys(value)
			else:
				ret[str(key)] = value
		return ret

	@classmethod
	def _ensure_sequence_string_keys(cls, sequence: Sequence):
		"""For every item of the sequence: recursively ensure that all possible dictionaries have string keys."""
		ret = list()
		for item in sequence:
			if isinstance(item, Mapping):
				ret.append(cls._ensure_mapping_string_keys(item))
			elif isinstance(item, Sequence):
				ret.append(cls._ensure_sequence_string_keys(item))
			else:
				ret.append(item)

		return ret


class Array(NativeValue, _NativeContainerMixin, Sequence):
	"""Icinga Array type.

	A sequence implementation here. Note that this type is not mutable (because Icinga seems not to support array item
	modification).
	"""

	def __init__(self, value, parent_descr):
		value = list(value)
		# Ensure string keys for every possible dict in the sequence
		value = self._ensure_sequence_string_keys(value)
		super().__init__(value, parent_descr)

	@classmethod
	def converter(cls, x):
		return list(x)

	def __getitem__(self, item):
		return self._convert_container(item, self._value.__getitem__(item))

	def __len__(self):
		return self._value.__len__()

	def __eq__(self, other):
		# Compare equal to both list and tuple
		try:
			return super().__eq__(other) or (list(other) == self.value and not isinstance(other, str))
		except TypeError:
			return NotImplemented


class Dictionary(NativeValue, _NativeContainerMixin, MutableMapping):
	"""Icinga Dictionary attribute type.

	This is also implemented as a dictionary here, but with some differences:
	- None is treated as an empty dict
	- All keys are (recursively) ensured to be strings, because Icinga only handles string keys
	- Any modification is propagated to the parent (if there is a parent), so that the parent can propagate to its \
		parent (and so on), so that the modification is send to Icinga
	"""

	def __init__(self, value, parent_descr):
		# Icinga may return (JSON) null (=Python None) for an empty dict (e.g. empty vars)
		value = value if value is not None else dict()
		# Ensure all keys are strings
		value = self._ensure_mapping_string_keys(value)
		super().__init__(value, parent_descr)

	@classmethod
	def converter(cls, x):
		# Icinga may return (JSON) null (=Python None) for an empty dict (e.g. empty vars)
		x = x if x is not None else dict()
		return dict(x)

	@staticmethod
	def parse_attrs(attrs):
		"""Parse attrs with :meth:`icinga2api_py.results.ResultSet.parse_attrs`."""
		if not isinstance(attrs, Sequence):
			# attrs is not a string, not a list and not a tuple...
			# Icinga itself handles only string keys in dictionaries, so attrs are converted to strings here
			attrs = str(attrs)
		return ResultSet.parse_attrs(attrs)

	def __getitem__(self, item):
		"""Mapping access with dot-syntax."""
		try:
			ret = self._value
			for item in self.parse_attrs(item):
				ret = ret[item]
			return self._convert_container(item, ret)
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

			if isinstance(value, Mapping):
				# Make sure all keys are strings to handle things like Icinga does
				temp[attrs[-1]] = self._ensure_mapping_string_keys(value)
			else:
				temp[attrs[-1]] = value

	def __setitem__(self, item, value):
		"""Set a value of a specific item."""
		self.modify({item: value})

	def __delitem__(self, item):
		"""Delete an item."""
		raise NoUserModify("Deleting an item is not supported (yet)")

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
