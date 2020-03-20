# -*- coding: utf-8 -*-
"""Basic things needed in most modules, and the base class of every mapped object (AbstractIcingaObject)."""

import enum


class TypeNumber(enum.Enum):
	"""Whether a type should be in singular or plural form, or not specified (irrelevant)."""

	#: Single object
	SINGULAR = 1
	#: Multiple objects
	PLURAL = 2
	#: Number of objects is unknown/irrelevant
	IRRELEVANT = 0


class ParentObjectDescription:
	"""Describe the parent object of an "AbstractIcingaObject" object.

	The "parent object" of an object A can be another "AbstractIcingaObject" B, in which case B has an field, whose
	value is A.	In this case, parent and field have to be known.
	In case an object has no parent (= is not a value for a field of another object), this description contains the
	session the object belongs to.
	The session attribute will reference to the session no matter which case is chosen. In case no session is given, the
	session reference is copied from the parent object.
	"""

	def __init__(self, session=None, parent: "AbstractIcingaObject" = None, field=None):
		"""Init the parent object description, also see class docstring.

		:param session: The session the object belongs to, can be None if parent and field is set.
		:param parent: The parent object of the described object.
		:param field: The field the described object is a value for the parent object.
		"""
		self.parent = parent
		self.field = field
		if parent is not None and field is not None:
			# Has a parent
			self.session = session or parent.parent_descr.session
		elif session is not None and parent is None and field is None:
			# The session is given and nothing else -> belongs to this session
			self.session = session
		elif session is not None:
			# Session is given but also either field or parent but not both...
			raise ValueError("Invalid parent object description parameters combination passed")
		else:
			# Invalid parameters
			raise ValueError("Unable to build a parent object description: too few information given with parameters")

	def decouple(self):
		"""Make sure the parent object descriptions is not coupled to a parent."""
		self.parent = None
		self.field = None

	def __eq__(self, other):
		return \
			self.session == other.session and \
			self.parent == other.parent and \
			self.field == other.field


class AbstractIcingaObject:
	"""Base class for every other class representing a Icinga type."""

	#: The DESC is overriden in subclasses with the Icinga type description
	DESC = {}
	#: The FIELDS is overriden in subclasses with all FIELDS and their description for the object type
	#: This includes the fields of parent classes of the subclass
	FIELDS = {}

	###################################################################################################################
	# Simplified access to DESC/FIELDS
	###################################################################################################################

	@property
	def type(self):
		"""The type of this/these object(s), always returns the singular name."""
		return self.DESC["name"]

	def _field_type(self, attr):
		"""Return type class for a field given by name.

		:raises KeyError: If the attr is not a field or its type name is not a valid type.
		"""
		typename = self.FIELDS[attr]["type"]
		# Field types are always singular
		return self.session.types.type(typename, number=TypeNumber.SINGULAR)

	def permissions(self, field):
		"""Get permission for a given attribute (field), returned as a tuple for the boolean values of:
		no_user_view, no_user_modify

		All values True is the default.
		"""
		try:
			field_desc = self.FIELDS[field]["attributes"]
		except KeyError:
			return True, True
		return field_desc.get("no_user_view", True), field_desc.get("no_user_modify", True)

	###################################################################################################################
	# Init object or convert to an object of this class, get parent_descr and session
	###################################################################################################################

	def __init__(self, *args, **kwargs):
		"""Init such an object.

		This requires a parent_descr parameter. If not given in **kwargs, the last positional parameter is used as
		parent_descr.
		"""
		args = list(args)
		self._parent_descr = kwargs.pop("parent_descr", None)

		if self._parent_descr is None:
			# Fallback: take last positional parameter as parent_descr
			try:
				self._parent_descr = args.pop()
			except IndexError:
				raise TypeError(f"{self.__class__.__name__} needs a parent_descr parameter to initialize successfully")

		super().__init__(*args, **kwargs)

	@property
	def parent_descr(self):
		"""Parent object description."""
		return self._parent_descr

	@property
	def session(self):
		"""The session such an object was created in."""
		return self.parent_descr.session

	@classmethod
	def convert(cls, obj, parent_descr):
		"""Return obj as an object of this class, raises TypeError or ValueError if conversion was not possible."""
		raise TypeError("Conversion to AbstractIcingaObject not possible")
