# -*- coding: utf-8 -*-
"""This module implements parsing of Icinga attributes as well as joins and filters.


"""

import collections.abc
import enum
import logging
from typing import Union, Optional, Sequence

LOGGER = logging.getLogger(__name__)

# TODO clarify naming of "Primary key" / "primary attribute" (and others)


class _PrimaryAttribute(enum.Enum):
	"""The primary attribute key."""

	ATTRS = "attrs"
	JOINS = "joins"
	NONE = None


#: The special attribute keys that are handled in parsing and are therfore illegal or ignored in some places
SPECIAL_ATTRIBUTE_KEYS = set((item.value for item in _PrimaryAttribute if item.value is not None))


class Attribute:
	"""Class representing an attribute of an Icinga object.

	To illustrate this, lets image a dict `{"a": {"b": "c"}, "x": {"y": "z"}` as an Icinga object. From a technincal
	view, you could say this object has two fields and four ("addressable") attributes:
	"a" and "x" are fields, in addition to those "a.b" and "x.y" are also attributes. As you can see, every field of
	any object is an attribute, but not every attribute is necessarily a field of an object.

	This Attribute class implements conversion between two distinctive attribute notations: results path and Icinga
	notation. The Icinga notation is propably more logical: [<object type>.]<field>[.<possible subattributes>]*
	This is what the Icinga API expects in e.g. filters (although the object type is not everywhere optional).
	The other notation describes the path for an attribute for an API result, and is propably less intuitive:
	(<attr>[.<attr>]*)|(attrs[.<attr>]*)|(joins[.<joined_type>[.<attr>]*])
	This notation is needed when accessing an attribute of a result. [TODO add reference to results and results comment]
	No matter which notation is chosen, an object of this class represents attributes in general - it understands both
	and can convert between these (which is actually one of its main intended usages).

	An object of this class may or may not know, which "object type" the object has of which it describes an attribute.
	This is called "awareness" here.
	A full attribute description needs the object's type for which it is describing an attribute (= it is
	"object_type_aware"). On the other hand, in many cases the type might not be known or irrelevant.

	When initiating an Attribute object, there are three arguments to care about. You may have a look at the
	tests/test_attrs module, which extensively tests init arguments in different combinations.
	Any object of this class is immutable, so changing things afterwards is not really possible - but there are methods
	provided to get objects different in a certain property.

	:param descr: Attribute description. By default the result path notation is assumed, except for when aware is set\
					to True.
	:param aware: Whether the first part of the passed descr is the object_type. False by default. Setting this to True\
					is roughly equivalent to setting object_type=descr[:descr.index('.')]
	:param object_type: The object type this attribute describes an attribute of.
	"""

	__slots__ = ("_primary_key", "_join_type", "_attrs", "_object_type")

	#: Attributes considered for cloning and comparison
	_object_attributes = ("_primary_key", "join_type", "attrs", "object_type")

	class Format(enum.Enum):
		"""Attribute representation format."""

		#: Format used to describe the "path" of an attribute for an Icinga API result (one in the results list)
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
		#: List of (sub) attributes, possibly empty.
		#: This is internally a list, but gets converted to a tuple for external usage (attrs property)
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

	@classmethod
	def _plain_init(cls, primary_key: _PrimaryAttribute, join_type: str, attrs: Sequence[str], object_type: str):
		"""Init with the private attributes of such an object."""
		# Build descr list
		builder = list()
		if primary_key != _PrimaryAttribute.NONE:
			builder.append(primary_key.value)
		if primary_key == _PrimaryAttribute.JOINS:
			builder.append(join_type)
		builder.extend(attrs)
		return cls(builder, object_type=object_type)

	@classmethod
	def enforce_attribute_type(cls, obj):
		"""Convert obj to an Attribute, or just return it if it already is one."""
		if isinstance(obj, cls):
			return obj
		object_type = getattr(obj, "object_type")
		return cls(obj, object_type=object_type)

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

	def amend_join_type(self, join_type: str):
		"""Return a new object, similar to this one but with the given joined object for which this attribute describes
		something."""
		join_type = join_type.lower()
		# Ensure not empty or None
		if not join_type:
			raise ValueError(f"Illegal join type: {join_type}")
		# Return new object with correct primary key and joined type
		return self._plain_init(_PrimaryAttribute.JOINS, join_type, self.attrs, self.object_type)

	@property
	def object_type(self):
		"""Return the object type this attribute is for - if it's aware of it's object type, None otherwise."""
		return self._object_type

	def amend_object_type(self, object_type: str):
		"""Set the object type this attribute is for."""
		# Ensure not empty or None
		if not object_type:
			raise ValueError(f"Illegal object type: {object_type}")

		attrs = self.attrs
		try:
			# Cut off first item if it's the object type
			attrs = attrs[1:] if attrs[0] == object_type else attrs
		except IndexError:
			pass
		return self._plain_init(self._primary_key, self.join_type, attrs, object_type)

	@property
	def attrs(self):
		"""Attributes as list."""
		return tuple(self._attrs)

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
		ret.extend(self.full_attrs(self.Format.RESULTS))
		return f"<{' '.join(ret)}>"

	def __hash__(self):
		return hash(repr(self))

	def __eq__(self, other):
		"""Compare to other attribute description, or return a filter object."""
		try:
			return all((getattr(self, attr) == getattr(other, attr) for attr in self.__class__._object_attributes))
		except AttributeError:
			...  # TODO return filter object


class AttributeSet(collections.abc.MutableSet):
	"""Represents a mutable list of attributes."""

	# TODO Implement a MutableSet here, that contains only Attribute objects

	# TODO implement checking attrs restrictions

	# TODO implement checking joins restrictions


class Filter:
	"""Represents an Icinga filter."""

	# TODO implement data structure to store filters easily

	# TODO implement operations (and, or, not, ...)
