# -*- coding: utf-8 -*-
"""This module is for creating the Icinga object types as Python classes."""

import threading
from ..results import CachedResultSet, Result
from .objects import IcingaObject


class Types(CachedResultSet):
	"""A class to create Python classes from the Icinga type definitions."""

	# Map simple Icinga types to Python type
	ICINGA_PYTHON_TYPES = {
		"Number": float,
		"String": str,
		"Boolean": bool,
		"Timestamp": float,  # Maybe that should be compareable to Python datetime?
		"Array": list,
		"Dictionary": dict,
		"Value": str,  # ???????????????????? # TODO check
		# Duration does not appear over API(?)
	}

	def __init__(self, session):
		"""Load all Icinga object types and setup creating them in classes.
		It's assumed, that the object type definitions do not change, so the cache time is set to never expire.
		Even if the data were loaded newly, the changes would only appear in newly created objects/classes."""
		super().__init__(session.api().types.get, float("inf"))
		self.iclient = session

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

	def type(self, item):
		"""Get an Icinga object type by its name. Both singular and plural names are accepted."""
		with self._lock:
			if item in self._classes:
				return self._classes[item]
			# Get type description from Icinga API
			type_desc, singular = self[item]
			# All fields for this type (also fields of base classes)
			fields = {}
			for name, desc in type_desc["fields"].items():
				try:
					if desc["type"] not in self.ICINGA_PYTHON_TYPES.values():
						desc["type"] = self.ICINGA_PYTHON_TYPES[desc["type"]]
				except KeyError:
					try:
						# Value type can be a type described in types
						desc["type"] = self.type(desc["type"])
					except (KeyError, ValueError, AttributeError):
						raise ValueError("Icinga object type {}: field {} has an unknown value type: {}".format(
							item, name, desc["type"]))
				fields[name] = desc

			try:
				parent = self.type(type_desc["base"])
			except KeyError:
				# No such type, or no "base" in the type descprion (second is more likely)
				# The Icinga API doc clearly states, that base is in every type description - but this is not the case!
				# -> TODO Icinga issue
				parent = IcingaObject

			# Merge fields of parent class into own fields
			fields.update(parent.FIELDS)
			# Namespace for dynamically created class
			namespace = {
				"__module__": self.__class__.__module__,
				"DESC": type_desc,
				"FIELDS": fields,
			}
			# TODO more namespace(?)

			# Create the class and store in the _classes dict to prevent creating it again
			ret = type(item.title(), (parent,), namespace)
			self._classes[item] = ret
			return ret
