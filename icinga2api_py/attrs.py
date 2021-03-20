# -*- coding: utf-8 -*-
"""This module implements parsing of Icinga attributes.


"""

import collections.abc
import enum
from typing import Union, Optional, Sequence, Iterable, Generator, Iterator

from .exceptions import AttributeParsingError
from .expressions import VariableExpression, Expression

__all__ = ["Attribute", "AttributeSet"]


class _LeadKey(enum.Enum):
	"""The leading attribute key."""

	ATTRS = "attrs"
	JOINS = "joins"
	NONE = None


#: The special attribute keys that are handled in parsing and are therfore illegal or ignored in some places
SPECIAL_ATTRIBUTE_KEYS = set((item.value for item in _LeadKey if item.value is not None))


class Attribute(VariableExpression):
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
	The object type can be given as a string with the object_type init argument, or setting it to True if the
	description contains the object type.

	When initiating an Attribute object, there are three arguments to care about. You may have a look at the
	tests/test_attrs module, which extensively tests init arguments in different combinations.
	Any object of this class is immutable, so changing things afterwards is not really possible - but there are methods
	provided to get objects different in a certain property.

	:param descr: Attribute description. By default the result path notation is assumed, except for when aware is set\
					to True.
	:param object_type: The object type this attribute describes an attribute of as a string, or True to read the type
					from the description (roughly equivalent to `object_type=descr[:descr.index('.')]`)
	"""

	__slots__ = ("_lead_key", "_join_type", "_attrs", "_object_type")

	#: Attributes considered for cloning and comparison
	_object_attributes = ("_lead_key", "join_type", "attrs", "object_type")

	class Format(enum.Enum):
		"""Attribute representation format."""

		#: Format used to describe the "path" of an attribute for an Icinga API result (one in the results list)
		RESULTS = enum.auto()
		#: The format Icinga uses for e.g. filters
		ICINGA = enum.auto()

	def __init__(
				self,
				descr: Union[str, Iterable[str]],
				object_type: Union[str, bool, None] = None
			):
		# Make sure the description is a list
		try:
			descr = descr.split('.')
		except AttributeError:
			# Assume that it's an iterable (already split at dots)
			descr = list(descr)

		# Get first item, check for too short descriptions
		try:
			first = descr.pop(0).lower()
		except IndexError:
			raise AttributeParsingError("Invalid attribute description: too short")

		# Defaults
		#: Lead attribute: internally kept _LeadKey that preceeds everything else
		self._lead_key = _LeadKey.NONE
		#: Join type or None
		self._join_type = None
		#: List of (sub) attributes, possibly empty.
		#: This is internally a list, but gets converted to a tuple for external usage (attrs property)
		self._attrs = descr

		try:
			object_type = object_type.lower()
		except AttributeError:
			if object_type:
				# Set awareness type by first description part
				object_type = first

		# Object type set, check that it's not a special key...
		if object_type in SPECIAL_ATTRIBUTE_KEYS:
			object_type = None

		#: For which type of an object the attribute description was created, or None if not aware of an object type.
		#: An empty string or any special attribute keys are not valid object types.
		#: None as object_type means this attribute is not object aware
		self._object_type = object_type

		# Get first+descr into these variables
		if first == "attrs":
			self._lead_key = _LeadKey.ATTRS
		elif first == "joins":
			self._lead_key = _LeadKey.JOINS
			try:
				self._join_type = descr.pop(0).lower()
				self._attrs = descr
			except IndexError:
				raise AttributeParsingError("Invalid attribute description: join but no joined type")
		elif object_type and first == object_type:
			# The first item is the object type
			self._lead_key = _LeadKey.ATTRS
		else:
			self._attrs = [first, *descr]

		# Call super's init method and therefore asign the lookup symbol
		super().__init__(".".join(iter(self)))

	@classmethod
	def _plain_init(
				cls, lead_key: _LeadKey, join_type: Optional[str], attrs: Sequence[str],
				object_type: Optional[str]
			) -> "Attribute":
		"""Init with the private attributes of such an object."""
		# Build descr list
		builder = list()
		if lead_key != _LeadKey.NONE:
			builder.append(lead_key.value)
		if lead_key == _LeadKey.JOINS and join_type:
			builder.append(join_type)
		builder.extend(attrs)
		return cls(builder, object_type=object_type)

	@classmethod
	def ensure_type(cls, obj) -> "Attribute":
		"""Ensure that obj is an Attrite object."""
		if not isinstance(obj, cls):
			if isinstance(obj, str):
				return Attribute(obj, ("." in obj))
			else:
				# Assume sequence
				return Attribute(obj, (len(obj) > 1))
		return obj

	@property
	def object_type_aware(self) -> bool:
		"""Whether or not this Attribute description is aware of for which object it was written."""
		return self._object_type is not None

	@property
	def join_type(self) -> Optional[str]:
		"""Get join type if this attribute describes a joined type or something in a joined type, else None."""
		if self._lead_key == _LeadKey.JOINS:
			return self._join_type
		return None

	def amend_join_type(self, join_type: str) -> "Attribute":
		"""Return a new object, similar to this one but with the given joined object for which this attribute describes
		something."""
		join_type = join_type.lower()
		# Ensure not empty or None
		if not join_type:
			raise ValueError(f"Illegal join type: {join_type}")
		# Return new object with correct lead key and joined type
		return self._plain_init(_LeadKey.JOINS, join_type, self.attrs, self.object_type)

	@property
	def object_type(self) -> Optional[str]:
		"""Return the object type this attribute is for - if it's aware of it's object type, None otherwise."""
		return self._object_type

	def amend_object_type(self, object_type: str, as_jointype=False, override_jointype=False) -> "Attribute":
		"""Set the object type for which this describes an attribute.

		By default the old object type is just overriden with the new one. But if as_jointype is True, the old object
		type is set as the join_type of the returned attribute. The additional parameter override_jointype does this
		also if there already is an join_type for this attribute.

		:param object_type: New object type to set
		:param as_jointype: Use old object type as new join type (if there an object type and no join type)
		:param override_jointype: Use old object type as new join type even if there already is a join type
		:return: New Attribute object with the new object type (and maybe also new jointype)
		"""
		if all((
			as_jointype,
			self.object_type,
			object_type != self.object_type,
			override_jointype or not self.join_type
		)):
			# If as_jointype and there is an old object_type (and it is not the same as the new one) and either there is
			# no old join_type or the join_type should be overriden:
			# Set old object_type as new join_type
			return self._plain_init(_LeadKey.JOINS, self.object_type, self.attrs, object_type)

		attrs = self.attrs
		try:
			# Cut of first item in case that specifies the object that is now set
			if attrs[0] == object_type and self._lead_key != _LeadKey.ATTRS:
				attrs = attrs[1:]
		except IndexError:
			pass
		if self.join_type == object_type:
			# Join type is new object type -> joins.<type> to attrs
			return self._plain_init(_LeadKey.ATTRS, None, attrs, object_type)
		return self._plain_init(self._lead_key, self.join_type, attrs, object_type)

	@property
	def attrs(self) -> Sequence[str]:
		"""Attributes as a sequence."""
		return tuple(self._attrs)

	def parent_attribute(self) -> Optional["Attribute"]:
		"""Return a parent attribute if there is one."""
		if self.attrs:
			return self._plain_init(self._lead_key, self.join_type, self.attrs[:-1], self.object_type)
		return None

	def full_attrs(self, form: Format = Format.RESULTS) -> Generator[str, None, None]:
		"""Iterate over the full attribute description parts."""
		if form == self.Format.ICINGA:
			type_ = self.join_type or self.object_type
			if type_:
				yield type_
			yield from self.attrs
		else:
			if self._lead_key != _LeadKey.NONE:
				yield self._lead_key.value
			if self.join_type is not None:
				yield self.join_type
			yield from self.attrs

	def description(self, form: Format = Format.RESULTS) -> str:
		"""Return the attribute description (= string representation) in the given format."""
		return ".".join(self.full_attrs(form))

	def __iter__(self) -> Iterator[str]:
		"""Iterate over the parts of the attribute description."""
		yield from self.full_attrs(self.Format.RESULTS)

	def __str__(self):
		"""Return the string representation of this attribute description."""
		return self.description(self.Format.ICINGA)

	def __repr__(self):
		"""Full string representation."""
		ret = [self.__class__.__name__]
		if self.object_type_aware:
			ret.append(f"[{self.object_type}]")
		ret.extend(self.full_attrs(self.Format.RESULTS))
		return f"<{' '.join(ret)}>"

	def __hash__(self):
		return hash(repr(self))

	def __eq__(self, other) -> Union[bool, Expression]:
		"""Compare to other attribute description, or return a filter object."""
		try:
			return all((getattr(self, attr) == getattr(other, attr) for attr in self.__class__._object_attributes))
		except AttributeError:
			return super().__eq__(other)

	def __ne__(self, other) -> Union[bool, Expression]:
		"""Compare to other attribute description, or return a filter object."""
		try:
			return all((getattr(self, attr) != getattr(other, attr) for attr in self.__class__._object_attributes))
		except AttributeError:
			return super().__ne__(other)


class AttributeSet(collections.abc.MutableSet):
	"""Represents a mutable set of attributes.

	The set always works with :class:`attrs.Attribute`s in the background, it will however accept other accepts other
	types and uses :method:`attrs.Attribute.ensure_type`.
	The attribute set can be type aware, which means that every of its attribute objects has the same object type (and
	therefore also is type aware of course).

	:param object_type: Set type awareness to this object type
	:param initial: Iterable of initial attributes to add
	"""

	def __init__(self, object_type: Optional[str] = None, initial: Iterable = None):
		#: The object type this list has attributes for
		self._object_type = object_type
		initial = (self._enforce_type(attr) for attr in (initial or tuple()))
		#: The internal set of Attribute objects
		self._attrs = set(initial)

	@property
	def object_type(self) -> Optional[str]:
		"""The object type this list has attributes for."""
		return self._object_type

	@object_type.setter
	def object_type(self, object_type: Optional[str]):
		"""Set a new object type."""
		self._object_type = object_type
		# Enforce new object type for all attribute objects
		initial = (self._enforce_type(attr) for attr in self._attrs)
		self._attrs = set(initial)

	def _enforce_type(self, attr) -> Attribute:
		"""Enforce the correct attribute type for attr."""
		attr = Attribute.ensure_type(attr)
		if attr.object_type != self._object_type:
			# Set new object type, set old object type as join type if join type was not set
			return attr.amend_object_type(self._object_type, as_jointype=True, override_jointype=False)
		return attr

	def add(self, attr):
		"""Add an attribute to this set of attributes."""
		self._attrs.add(self._enforce_type(attr))

	def discard(self, attr) -> None:
		"""Discard an attr of this set of attributes (does nothing if the attr is not in this set)."""
		self._attrs.discard(self._enforce_type(attr))

	def __contains__(self, attr) -> bool:
		"""Returns True if the given attr is contained in this set of attributes."""
		if attr is None:
			# The main use case is to break the recursion
			return False
		attr = self._enforce_type(attr)
		# Check whether this attribute object is in the set, check recursively for parent attributes
		return attr in self._attrs or (attr.parent_attribute() in self)

	def __len__(self):
		"""Returns the number of attributes this set has."""
		return len(self._attrs)

	def __iter__(self) -> Iterator[Attribute]:
		"""Iterate over the Attribute objects of this set."""
		return iter(self._attrs)
