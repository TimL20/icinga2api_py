# -*- coding: utf-8 -*-
"""Basic object classes used in ORM subpackage."""


class IcingaObject:
	"""Representation of an Icinga object. Subclasses of this class should be created with IcingaObjectClass."""
	def __init__(self):
		pass  # TODO implement

	def __getattr__(self, attr):
		if attr in self.fields:
			pass  # TODO implement

		# else
		raise AttributeError

	def __setattr__(self, key, value):
		pass # TODO implement modifying the object
