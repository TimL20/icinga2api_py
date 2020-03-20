# -*- coding: utf-8 -*-
"""This module is responsible for creating the Icinga object types as Python classes."""

import threading
from ..results import CachedResultSet, Result
from .simple_types import Number, String, Boolean, Value, Array, Dictionary, Timestamp
from .complex_types import IcingaObject, IcingaObjects, IcingaConfigObject, IcingaConfigObjects
from .base import TypeNumber, AbstractIcingaObject


class Types(CachedResultSet):
	"""A class to create Python classes from the Icinga type definitions."""

	#: Map some Icinga object types directly to Python types (lowercase to handle things case-insensitive)
	ICINGA_PYTHON_TYPES = {
		# Base classes for everything else...
		"object": IcingaObject,
		"objects": IcingaObjects,
		# Configuration objects are what this IOM part is all about, they have special classes
		"configobject": IcingaConfigObject,
		"configobjects": IcingaConfigObjects,

		# Mapping of simple types defined in the simple_types module
		"number": Number,
		"string": String,
		"boolean": Boolean,
		"timestamp": Timestamp,
		"array": Array,
		"dictionary": Dictionary,
		"value": Value,
		# Duration does not appear over API(?)
	}

	def __init__(self, session):
		"""Load all Icinga object types and setup creating them as classes.

		It's assumed, that the object type definitions do not change, so the cache time is set to infinity.
		Even if the data were loaded newly, the changes would only appear in newly created objects/classes.
		"""
		super().__init__(request=session.api().types.get, cache_time=float("inf"))
		self.iclient = session

		# Lock to make type creation thread-safe, althought the whole library is not guaranteed to be
		self._lock = threading.RLock()

		# Created type classes
		self._classes = {}

	def result(self, item):
		"""Behaves like parent class when called with item of type int or slice.
		The other functionality is to return a Result representing a type's description when called with a name of a
		type. The Result is in this case returned as a tuple together with a Boolean, which is False if the name was a
		plural name instead of singular name."""
		if isinstance(item, int) or isinstance(item, slice):
			return super().result(item)

		# Search for type with this name (all lowercase)
		typename = item.lower()
		for type_desc in self:
			if type_desc["name"].lower() == typename:
				return Result(type_desc), True
			if type_desc["plural_name"].lower() == typename:
				return Result(type_desc), False

		# Not found
		raise KeyError("Found no such type: {}".format(item))

	def type(self, item, number=TypeNumber.IRRELEVANT):
		"""Get an Icinga object type by its name.

		Both singular and plural names are accepted.
		A class for the type given by string is returned. It's possible to specify whether to return the singular or
		the plural type.
		"""
		# Handle singular/plural first, to avoid problems related to that in general
		if number == TypeNumber.SINGULAR:
			item = item[:-1] if item[-1] == 's' else item
		elif number == TypeNumber.PLURAL:
			item = item + 's' if item[-1] != 's' else item
		else:
			number = TypeNumber.PLURAL if item[-1] == 's' else TypeNumber.PLURAL

		if item.lower() in self.ICINGA_PYTHON_TYPES:
			# Types mapped directly for advanced functionality
			return self.ICINGA_PYTHON_TYPES[item.lower()]

		with self._lock:
			if item in self._classes:
				# Already created
				return self._classes[item]
			# Get type description from Icinga API
			type_desc, singular = self[item]
			# All fields for this type (also fields of base classes)
			fields = {}
			for name, desc in type_desc["fields"].items():
				fields[name] = desc

			try:
				parent = self.type(type_desc["base"], number)
			except KeyError:
				# No such type, or no "base" in the type descprion (second is more likely)
				# The Icinga API doc clearly states, that base is in every type description - but this is not the case!
				# -> TODO Icinga issue

				# Default parent class
				# AbstractIcingaObject is the same for singular and plural
				# Not IcingaObject(s) class, because the type could be e.g. "Number" in this case
				parent = AbstractIcingaObject

			# Classname for created class is the type name
			classname = type_desc["name"] if number == TypeNumber.SINGULAR else type_desc["plural_name"]
			# Merge fields of parent class into own fields
			fields.update(parent.FIELDS)
			# Namespace for dynamically created class
			namespace = {
				"__module__": self.__class__.__module__,
				"DESC": type_desc,
				"FIELDS": fields,
			}

			# Create the class and store in the _classes dict to prevent creating it again
			ret = type(classname, (parent,), namespace)
			self._classes[item] = ret
			return ret
