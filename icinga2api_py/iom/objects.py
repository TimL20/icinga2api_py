# -*- coding: utf-8 -*-
"""This module contains funcionality for all mapped objects.

The classes for the mapped Icinga objects are created in the types module, but every class created there inherits from
a class here."""


class IcingaObject:
	"""Representation of an Icinga object. Subclasses of this class should be created with IcingaObjectClass."""
	def __init__(self, session):
		pass  # TODO implement

	def __getattr__(self, attr):
		if attr in self.fields:
			pass  # TODO implement

		# attribute not in fields
		raise AttributeError

	def __setattr__(self, key, value):
		pass # TODO implement modifying the object
