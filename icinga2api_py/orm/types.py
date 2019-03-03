# -*- coding: utf-8 -*-
"""This module is for creating the Icinga object types as Python classes."""

import threading
from ..results import CachedResultSet, Result
from .objects import IcingaObject


class Types(CachedResultSet):
	# Map Icinga type -> Python type
	ICINGA_PYTHON_TYPES = {
		"Number": float,
		"String": str,
		"Boolean": bool,
		"Timestamp": float,  # Maybe that should be compareable to Python datetime?
		"Array": list,
		"Dictionary": dict,
		"Value": str,  # ????????????????????
		# Duration does not appear over API(?)
	}

	def __init__(self, iclient):
		super().__init__(iclient.api().types.get, float("inf"))
		self.iclient = iclient

		self._lock = threading.Lock()

		# Created type classes
		self._classes = {}

	def result(self, item):
		if isinstance(item, int) or isinstance(item, slice):
			return super().result(item)

		# Search for type with this name
		for type_desc in self:
			if type_desc["name"] == item:
				return Result(type_desc), True
			if type_desc["plural_name"] == item:
				return Result(type_desc), False

		# Not found
		raise KeyError("Found no such type")

	def __getattr__(self, item):
		with self._lock:
			if item in self._classes:
				return self._classes[item]
			type_desc, singular = self[item]
			for name, desc in type_desc["fields"].items():
				try:
					if desc["type"] not in self.ICINGA_PYTHON_TYPES.values():
						desc["type"] = self.ICINGA_PYTHON_TYPES[desc["type"]]
				except KeyError:
					try:
						desc["type"] = getattr(self, desc["type"])
						if desc["type"] is None:
							raise
					except (KeyError, ValueError, AttributeError):
						raise ValueError("Icinga type {} field {} has an unknown type: {}".format(item, name, desc["type"]))

			# Get base class, IcingaObject as default
			parent = getattr(self, type_desc["base"], None) if "base" in type_desc else IcingaObject

			namespace = {"__module__": self.__class__.__module__}
			# TODO more namespace?

			ret = type(item, (parent,), namespace)
			self._classes[item] = ret
			return ret
