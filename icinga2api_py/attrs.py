# -*- coding: utf-8 -*-
"""This module implements parsing of Icinga attributes as well as joins and filters.


"""

import enum
import logging
from typing import Union, Optional, Sequence

from . import exceptions

LOGGER = logging.getLogger(__name__)


class _PrimaryAttribute(enum.Enum):
	"""The primary attribute key."""

	ATTRS = "attrs"
	JOINS = "joins"
	NONE = None


#: The special attribute keys that are handled in parsing and are therfore illegal or ignored in some places
SPECIAL_ATTRIBUTE_KEYS = set((item.value for item in _PrimaryAttribute if item.value is not None))


class Attribute:
	"""Class representing an attribute of an Icinga object.

	# TODO describe type awareness
	# TODO describe attrs and joins handling
	"""

	#: Attributes considered for cloning and comparison
	_object_attributes = ("_primary_key", "join_type", "attrs", "object_type")

	class Format(enum.Enum):
		"""Attribute representation format."""

		#: Format as used for the results
		RESULTS = enum.auto()
		#: The format Icinga uses for e.g. filters
		ICINGA = enum.auto()

	def __init__(self,
				descr: Union[str, Sequence[str]],
				aware: bool = False,
				object_type: Optional[str] = None
			):
		# Make sure the description is a list
		try:
			descr = descr.split('.')
		except AttributeError:
			descr = list(descr)

		# Get first item, check for too short descriptions
		try:
			first = descr.pop(0).lower()
		except IndexError:
			raise ValueError("Invalid attribute description: too short")

		# Defaults
		#: Primary key: internally kept _PrimaryAttribute
		self._primary_key = _PrimaryAttribute.NONE
		#: Join type or None
		self._join_type = None
		#: List of (sub) attributes, possibly empty
		self._attrs = descr
		#: For which type of an object the attribute description was created, or None if not aware of an object type.
		#: An empty string or any special attribute keys are not valid object types.
		self._object_type = object_type.lower() if object_type and object_type not in SPECIAL_ATTRIBUTE_KEYS else None

		# Get first+descr into these variables
		if first == "attrs":
			self._primary_key = _PrimaryAttribute.ATTRS
		elif first == "joins":
			self._primary_key = _PrimaryAttribute.JOINS
			try:
				self._join_type = descr.pop(0).lower()
				self._attrs = descr
			except IndexError:
				pass  # descr was "joins", which is OK
		elif object_type and first == object_type:
			# The first item is the object type
			self._primary_key = _PrimaryAttribute.ATTRS
		elif aware and first not in SPECIAL_ATTRIBUTE_KEYS:
			# The first item is assumed to be the object type
			self._primary_key = _PrimaryAttribute.ATTRS
			self._object_type = first
		else:
			self._attrs = [first, *descr]

	@property
	def object_type_aware(self):
		"""Whether or not this Attribute description is aware of for which object it was written."""
		return self._object_type is not None

	@property
	def join_type(self):
		"""Get join type if this attribute describes a joined type or something in a joined type, else None."""
		if self._primary_key == _PrimaryAttribute.JOINS:
			return self._join_type
		return None

	@join_type.setter
	def join_type(self, type_: str):
		"""Set the type of the joined object for which this attribute describes something."""
		type_ = type_.lower()
		# Ensure not empty or None
		if not type_:
			raise ValueError(f"Illegal join type: {type_}")
		# Ensure the correct primary key
		self._primary_key = _PrimaryAttribute.JOINS
		self._join_type = type_

	@property
	def object_type(self):
		"""Return the object type this attribute is for - if it's aware of it's object type, None otherwise."""
		return self._object_type

	@object_type.setter
	def object_type(self, type_: str):
		"""Set the object type this attribute is for."""
		# Ensure not empty or None
		if not type_:
			raise ValueError(f"Illegal object type: {type_}")
		if self._primary_key == _PrimaryAttribute.NONE:
			try:
				if self._attrs[0] == type_:
					self._attrs.pop(0)
			except IndexError:
				pass
		self._object_type = type_

	@property
	def attrs(self):
		"""Attributes as list."""
		return self._attrs

	# TODO implement appending attr with / or getattr

	def full_attrs(self, form: Format = Format.RESULTS):
		"""Iterate over the full attribute description parts."""
		if form == self.Format.ICINGA:
			type_ = self.join_type or self.object_type
			if type_:
				yield type_
			yield from self.attrs
		else:
			if self._primary_key != _PrimaryAttribute.NONE:
				yield self._primary_key.value
			if self.join_type is not None:
				yield self.join_type
			yield from self.attrs

	def description(self, form: Format = Format.ICINGA):
		"""Return the attribute description (= string representation) in the given format."""
		return ".".join(self.full_attrs(form))

	def __iter__(self):
		"""Iterate over the parts of the attribute description."""
		yield from self.full_attrs(self.Format.RESULTS)

	def __str__(self):
		"""Return the string representation of this attribute description."""
		return self.description(self.Format.RESULTS)

	def __repr__(self):
		"""Full string representation."""
		ret = [self.__class__.__name__]
		if self.object_type_aware:
			ret.append(f"[{self.object_type}]")
		ret.append(self.description(self.Format.RESULTS))
		return f"<{' '.join(ret)}>"

	def __eq__(self, other):
		"""Compare to other attribute description, or return a filter object."""
		try:
			return all((getattr(self, attr) == getattr(other, attr) for attr in self.__class__._object_attributes))
		except AttributeError:
			...  # TODO return filter object


# TODO attrs restrictions
# TODO joins restrictions

# TODO add class representing a (mutable) attribute list

# TODO add a class representing a filter
