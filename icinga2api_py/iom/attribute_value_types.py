# -*- coding: utf-8 -*-
"""This module defines attribute value types.
As IcingaObjects can also be attribute values (as reference e.g. ´host_name´ in Service
or directly e.g. ´last_check_result´ in Checkable) this is also linked to the objects module...

There is also a JSON Encoder in this module, that is able to encode all AttributeValue objects.
Below the encoder is a JSON decoder helper, that provides a object_pairs_hook method for decoding."""

from json import JSONEncoder
from .types import Number
from .objects import IcingaObject


class AttributeValue:
	"""Base class for all attribute value types.
	The tasks are the following conversions:
	- Icinga value to Python object
	- Python object of this class to Icinga value
	- Other Python object to Python object of this class (convert)"""
	def __init__(self, parent_object, attribute, value):
		"""Init attribute value object with
		:param parent_object: the object of which this is a attribute value
		:param attribute: the attribute name of the attribute (of the parent_object)
		:param value: The attribute value as delivered from Icinga
		"""
		self._parent_object = parent_object
		self._attribute = attribute
		self._value = value

	@classmethod
	def convert(cls, value):
		"""Convert other Python object to an object of this class if possible."""
		return cls(None, None, value)

	@classmethod
	def direct_convert(cls, value):
		"""Convert other Python object to Icinga value that would also result from ´cls.convert(value).value()´.
		The default implementation is a fallback for subclasses."""
		return cls.convert(value).value()

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
	def convert(cls, value):
		"""Other Python object to an object ot this class."""
		return super().convert(cls.converter(value))

	@classmethod
	def direct_convert(cls, value):
		"""Python object to Icinga value."""
		cls.converter(value)


def create_native_attribute_value_type(name, converter=None):
	"""Create a NativeAttributeValue class using a converter."""
	if converter:
		return type(name, (AttributeValue, ), {"converter": converter, "__module__": AttributeValue.__module__})
	else:
		return type(name, (AttributeValue, ), {"__module__": AttributeValue.__module__})


class Timestamp(AttributeValue):
	"""Icinga timestamp attribute type. A float on the Icinga side, float and datetime here."""
	# TODO implement


class Duration(AttributeValue):
	"""Icinga duration attribute type. A string on Icinga side, union of string and float here."""
	# TODO implement


class Array(AttributeValue):
	"""Icinga Array attribute type. A sequence here."""
	# TODO implement


class Dictionary(AttributeValue):
	"""Icinga Dictionary attribute type. Also something like a dictionary here."""
	# TODO implement


class ObjectAttributeValue(Dictionary, IcingaObject):
	"""IcingaObject as an attribute value. Inherits from Dictionary, because these objects are represented as JSON dicts
	anyway."""
	# TODO implement (or remove if not needed)


class JSONResultEncoder(JSONEncoder):
	"""Encode Python representation of result(s) to JSON."""
	def default(self, o):
		if isinstance(o, AttributeValue):
			# Just serialize the value
			return super().default(o.value())

		# TODO use diect_convert of the appropriate class somehow???
		super().default(o)


class JSONResultDecodeHelper:
	"""Helperfor decode JSON encoded results. Provides a object_pairs_hook."""
	def __init__(self, parent_object):
		self._parent_object = parent_object

	def object_pairs_hook(self, pairs):
		"""The object_pairs_hook for JSON-decoding."""
		res = {}
		for key, value in pairs:
			if key == "results":
				# Final conversion for everything else than list and dict depending on the parent_object's fields
				self.final_conversion(value)
			res[key] = value
		return res

	def final_conversion(self, *objects):
		"""Final type conversion for every object passed. The conversion depends on the parent_object's fields and their
		types."""
		# Return value
		ret = []
		# Iterate over objects
		for obj in objects:
			# New object
			res = {}
			for key, value in obj.items():
				type_ = self._parent_object.FIELDS[key]["type"]
				self._parent_object.session.types.type(type_, Number.SINGULAR)
				if type_:
					res[key] = type_(self._parent_object, key, value)
				else:
					# No type conversion at all, because explicitely suppressed or type is not supported
					res[key] = value

			ret.append(res)

		return ret
