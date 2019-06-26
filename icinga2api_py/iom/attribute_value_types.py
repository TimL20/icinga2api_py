# -*- coding: utf-8 -*-
"""This module defines attribute value types.
As IcingaObjects can also be attribute values (as reference e.g. ´host_name´ in Service
or directly e.g. ´last_check_result´ in Checkable) this is also linked to the objects module..."""

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
	Basically just implements type conversion and requires the CONVERTER to do all the work or raise errors.
	The default implementation does nothing, but overriding the CONVERTER (in subclasses) makes it useful."""
	CONVERTER = lambda x: x

	@classmethod
	def convert(cls, value):
		return super().convert(cls.CONVERTER(value))

	@classmethod
	def direct_convert(cls, value):
		cls.CONVERTER(value)


def create_native_attribute_value_type(name, converter):
	"""Create a NativeAttributeValue class using a converter."""
	return type(name, (AttributeValue, ), {"CONVERTER": converter})


class ObjectAttributeValue(AttributeValue, IcingaObject):
	"""IcingaObject as an attribute value."""
	# TODO implement (or remove if not needed)


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
