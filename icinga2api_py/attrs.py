# -*- coding: utf-8 -*-
"""This module implements parsing of Icinga attributes as well as joins and filters.


"""

import abc
import collections.abc
import enum
import logging
from typing import Union, Optional, Any, Sequence, Iterable, Generator, Iterator, Callable
import operator as op
import re

from .exceptions import AttributeParsingError, FilterParsingError

LOGGER = logging.getLogger(__name__)

__all__ = ["Attribute", "AttributeSet", "Operator", "Filter"]

# TODO clarify naming of "Primary key" / "primary attribute" (and others)


class _PrimaryAttribute(enum.Enum):
	"""The primary attribute key."""

	ATTRS = "attrs"
	JOINS = "joins"
	NONE = None


#: The special attribute keys that are handled in parsing and are therfore illegal or ignored in some places
SPECIAL_ATTRIBUTE_KEYS = set((item.value for item in _PrimaryAttribute if item.value is not None))

#: Patterns for Icinga literals + converter callables (or None if not converted)
_LITERAL_PATTERNS = (
	# String literals
	(re.compile(r'".*"'), None),
	# Boolean literals
	(re.compile(r"true"), lambda _: True), (re.compile(r"false"), lambda _: False),
	# Null/None
	(re.compile(r"null"), lambda _: None),
	# Dictionary literals (not parsed as an operand)
	(re.compile(r"{.*}"), None),
	# Array literals (not parsed as an operand)
	(re.compile(r"\[.*\]"), None),
	# Duration literals
	(re.compile(r"[-+]?((\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?(ms|s|m|h|d)?)+"), None),
	# Number literals (exponents are not mentioned in Icinga docs)
	(re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?"), float),
)


class Operand(abc.ABC):
	"""Operand: something on which an operation is performed."""

	@staticmethod
	def possible_attribute(string: str) -> bool:
		"""Returns True if the given string is possibly an Attribute."""
		return not any(pattern.fullmatch(string) for pattern, converter in _LITERAL_PATTERNS)

	@abc.abstractmethod
	def __str__(self):
		return ""

	def __eq__(self, other):
		return self.filter(BuiltinOperator.EQ, other)

	def __ne__(self, other):
		return self.filter(BuiltinOperator.NE, other)

	def __lt__(self, other):
		"""Create a filter comparing this attribute to a value."""
		return self.filter(BuiltinOperator.LT, other)

	def __le__(self, other):
		"""Create a filter comparing this attribute to a value."""
		return self.filter(BuiltinOperator.LE, other)

	def __ge__(self, other):
		"""Create a filter comparing this attribute to a value."""
		return self.filter(BuiltinOperator.GE, other)

	def __gt__(self, other):
		"""Create a filter comparing this attribute to a value."""
		return self.filter(BuiltinOperator.GT, other)

	def filter(self, operator: "Operator", value):
		"""Create a Filter object representing a simple filter for this object compared to a certain value."""
		return Filter.simple(self, operator, value)


class ValueOperand(Operand):
	"""Value used for an operation."""
	def __init__(self, value):
		self.value = value

	def is_possible_attribute(self) -> bool:
		"""Whether this operand could possibly be an attribute."""
		try:
			return self.possible_attribute(self.value)
		except TypeError:
			return False  # In case the value is not a string

	@classmethod
	def create_with_type(cls, value):
		"""Create a ValueOperand guessing the correct type of value."""
		try:
			for pattern, converter in _LITERAL_PATTERNS:
				if pattern.fullmatch(value):
					return cls(converter(value))
		except TypeError:
			return value

	def __str__(self):
		return str(self.value)

	def __repr__(self):
		return f"<{self.__class__.__name__} {repr(self.value)}>"

	def __eq__(self, other):
		try:
			return self.value == other.value
		except AttributeError:
			return self.filter(BuiltinOperator.EQ, other)

	def __ne__(self, other):
		try:
			return self.value != other.value
		except AttributeError:
			return self.filter(BuiltinOperator.NE, other)


class Attribute(Operand):
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

	def __init__(
				self,
				descr: Union[str, Iterable[str]],
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
			raise AttributeParsingError("Invalid attribute description: too short")

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
				raise AttributeParsingError("Invalid attribute description: join but no joined type")
		elif object_type and first == object_type:
			# The first item is the object type
			self._primary_key = _PrimaryAttribute.ATTRS
		elif aware and first not in SPECIAL_ATTRIBUTE_KEYS:
			# The first item is assumed to be the object type
			self._primary_key = _PrimaryAttribute.ATTRS
			self._object_type = first
		else:
			self._attrs = [first, *descr]

	# TODO implement Array item acces via [index]

	@classmethod
	def _plain_init(
				cls, primary_key: _PrimaryAttribute, join_type: Optional[str], attrs: Sequence[str],
				object_type: Optional[str]
			) -> "Attribute":
		"""Init with the private attributes of such an object."""
		# Build descr list
		builder = list()
		if primary_key != _PrimaryAttribute.NONE:
			builder.append(primary_key.value)
		if primary_key == _PrimaryAttribute.JOINS and join_type:
			builder.append(join_type)
		builder.extend(attrs)
		return cls(builder, object_type=object_type)

	@classmethod
	def ensure_type(cls, obj) -> "Attribute":
		"""Ensure that obj is an Attrite object."""
		if not isinstance(obj, cls):
			if isinstance(obj, str):
				return Attribute(obj, aware=("." in obj))
			else:
				# Assume sequence
				return Attribute(obj, aware=(len(obj) > 1))
		return obj

	@property
	def object_type_aware(self) -> bool:
		"""Whether or not this Attribute description is aware of for which object it was written."""
		return self._object_type is not None

	@property
	def join_type(self) -> Optional[str]:
		"""Get join type if this attribute describes a joined type or something in a joined type, else None."""
		if self._primary_key == _PrimaryAttribute.JOINS:
			return self._join_type
		return None

	def amend_join_type(self, join_type: str) -> "Attribute":
		"""Return a new object, similar to this one but with the given joined object for which this attribute describes
		something."""
		join_type = join_type.lower()
		# Ensure not empty or None
		if not join_type:
			raise ValueError(f"Illegal join type: {join_type}")
		# Return new object with correct primary key and joined type
		return self._plain_init(_PrimaryAttribute.JOINS, join_type, self.attrs, self.object_type)

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
			return self._plain_init(_PrimaryAttribute.JOINS, self.object_type, self.attrs, object_type)

		attrs = self.attrs
		try:
			# Cut off first item if it's the object type
			attrs = attrs[1:] if attrs[0] == object_type else attrs
		except IndexError:
			pass
		if self.join_type == object_type:
			# Join type is new object type -> joins.<type> to attrs
			return self._plain_init(_PrimaryAttribute.ATTRS, None, attrs, object_type)
		return self._plain_init(self._primary_key, self.join_type, attrs, object_type)

	@property
	def attrs(self) -> Sequence[str]:
		"""Attributes as a sequence."""
		return tuple(self._attrs)

	def parent_attribute(self) -> Optional["Attribute"]:
		"""Return a parent attribute if there is one."""
		if self.attrs:
			return self._plain_init(self._primary_key, self.join_type, self.attrs[:-1], self.object_type)
		return None

	def full_attrs(self, form: Format = Format.RESULTS) -> Generator[str, None, None]:
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

	def __eq__(self, other) -> Union[bool, "Filter"]:
		"""Compare to other attribute description, or return a filter object."""
		try:
			return all((getattr(self, attr) == getattr(other, attr) for attr in self.__class__._object_attributes))
		except AttributeError:
			return self.filter(BuiltinOperator.EQ, other)

	def __ne__(self, other) -> Union[bool, "Filter"]:
		"""Compare to other attribute description, or return a filter object."""
		try:
			return all((getattr(self, attr) != getattr(other, attr) for attr in self.__class__._object_attributes))
		except AttributeError:
			return self.filter(BuiltinOperator.NE, other)


class AttributeSet(collections.abc.MutableSet):
	"""Represents a mutable list of attributes."""

	def __init__(self, object_type: Optional[str], initial: Iterable = None):
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
		# Enforce new object type for
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


#: Pattern for "usual" operators
_USUAL_OPERATOR_PATTERN = re.compile(r"[a-zA-Z_][\w_]*")
#: Pattern for functions and methods
_FUNCTION_PATTERN = re.compile(r"[^\w\s().,[\]]+")


class Operator:
	"""Operator used in filters."""

	class Type(enum.IntEnum):
		"""Type of Operator."""

		#: Unary operators
		UNARY = 0b000
		#: Comparative operators
		COMPARISON = 0b010
		#: Non-unary logical operators
		LOGICAL = 0b011
		#: Function
		FUNCTION = 0b100
		#: Method (executed *on* an attribute, not with)
		METHOD = 0b110

		@property
		def spaced(self) -> bool:
			"""True if this kind of operator should be separated by spaces."""
			return bool(0b1 & self)

		@property
		def pos(self) -> bool:
			"""False if the operator is written before the first operand, True otherwise."""
			return bool(0b10 & self)

		@property
		def call(self) -> bool:
			"""True if this operator requires a function call."""
			return bool(0b100 & self)

		@property
		def minimum_operands(self) -> int:
			"""Return the number of minimum operands needed."""
			if self == self.UNARY or self.call:
				return 1
			else:
				return 2

		@property
		def pattern(self):
			"""Return pattern this operator type is required to match."""
			if self.call:
				return _USUAL_OPERATOR_PATTERN
			# Usual operator: no alphanumeric character, no space, no brackets, no dot, no comma
			return _FUNCTION_PATTERN

	#: Translate operator string -> Operator object
	_OPERATOR_TRANSLATION = dict()

	def __init__(self, symbol, type_: Type, precedence: Optional[int] = None, func: Optional[Callable] = None):
		symbol = str(symbol)
		# Check symbol for compliance
		if not type_.pattern.match(symbol):
			raise ValueError("Operator symbol not compliant with the pattern of this operator type")
		#: Symbol (string) for this operator
		self.symbol = symbol
		#: Type of this operator
		self.type = type_
		#: Precedence of this operator
		self.precedence = precedence or (10 if type_.call else 99)
		#: Function that executes the operation
		self.operate = func

	def register(self, force=False):
		"""Register this operator for translation (used in filter parsing etc.)."""
		if force:
			self._OPERATOR_TRANSLATION[self.symbol] = self
			return True
		self._OPERATOR_TRANSLATION.setdefault(self.symbol, self)
		return self._OPERATOR_TRANSLATION[self.symbol] is self

	@classmethod
	def from_string(cls, string) -> "Operator":
		"""Get registered operator by string, raises KeyError if not found."""
		return cls._OPERATOR_TRANSLATION[string]

	@classmethod
	def all_operators(cls) -> Iterable["Operator"]:
		"""Return all operators, sorted by precedence."""
		return sorted((operator for operator in cls._OPERATOR_TRANSLATION.values()), key=op.attrgetter("precedence"))

	@property
	def is_executable(self) -> bool:
		"""Whether this operator is executable (locally)."""
		return self.operate is not None

	def __eq__(self, other):
		try:
			return self.symbol == other.symbol and self.operate is other.operate
		except AttributeError:
			return NotImplemented

	def __str__(self):
		return self.symbol

	def print(self, *operands):
		"""Return a string that represents the operation done on the given args."""
		def ops() -> Generator[str, None, None]:
			"""Generator to get operands in usable form."""
			for operand in operands:
				string = str(operand)
				# Precedence paranthesis (but not for method/function call parameters)
				if isinstance(operand, Filter) and operand.operator.precedence > self.precedence and not self.type.call:
					string = f"({string})"
				yield string

		# Check number of operands
		if len(operands) < self.type.minimum_operands:
			raise TypeError(f"{self.type.name.title()} operator needs more than {len(operands)} operand(s)")
		if self.type.pos:
			if self.type.call:
				# Method: <attribute>.<method>(value1, value2, ...)
				return f"{str(operands[0])}.{self.symbol}({', '.join(list(ops())[1:])})"
			else:  # call
				if self.type.spaced:
					return f" {self.symbol} ".join(ops())
				else:  # spaced
					return f"{self.symbol}".join(ops())
		else:  # pos
			if self.type.call:
				# Function: <function>(<operand1>, <operand2>, ...)
				return f"{self.symbol}({', '.join(ops())})"
			else:  # call
				# Unary operator: <operator><attribute>
				if len(operands) > 1:
					raise TypeError(f"Unary operator needs exactly one operand")
				return f"{self.symbol}{list(ops())[0]}"


class BuiltinOperator(Operator, enum.Enum):
	"""Simple operators that build on builtin operators."""

	def __new__(cls, *args):
		return Operator.__new__(cls)

	def __init__(self, *args):
		Operator.__init__(self, *args)
		self.register(True)

	# Simple unary operators
	NOT = ("!", Operator.Type.UNARY, 20, (lambda x: not x))
	# Simple comparison
	LT = ("<", Operator.Type.COMPARISON, 60, op.lt)
	LE = ("<=", Operator.Type.COMPARISON, 60, op.le)
	EQ = ("==", Operator.Type.COMPARISON, 60, op.eq)
	NE = ("!=", Operator.Type.COMPARISON, 60, op.ne)
	GE = (">=", Operator.Type.COMPARISON, 60, op.ge)
	GT = (">", Operator.Type.COMPARISON, 60, op.gt)
	# Simple logical operators
	OR = ("||", Operator.Type.LOGICAL, 120, (lambda *args: any(args)))
	AND = ("&&", Operator.Type.LOGICAL, 130, (lambda *args: all(args)))


class Filter(Operand):
	"""Represents an Icinga filter.

	- Simple filters consist of: attribute, operator, value   # TODO check whether something like 1==1 is possible
		- Simple filters are joined with logical operators (&&, ||)
		- Simple comparative operators compare an values of the specified attribute to the specified value
		- But methods for attriute objects are also allowed (e.g. contains on a dictionary)
			- Fully implementing that without using IOM is at least very difficult, if not impossible
			- An implementation that is at least better (not necessarily complete) can be done with IOM
		- Also global functions taking attribute values are possible to use in filters, e.g. match, regex, typeof, ...
			- It seems to be possible to add global functions via configuration
			- This seems therefore impossible to fully implement
		- Additionally there are unary operators
		- And also there is the possibility that there is no operator at all, in this case it's similar to Python's
			automatic bool() interpretation in if-clauses (e.g. empty strings are False), but also checks whether this
			attribute is defined (True if defined, False if not)
	- Nesting any filters with explicit precedence is possible

	Taking these things into account, it is at least *very, very* difficult to implement filters in a way, that this
	library can fully emulate the filtering of Icinga; it propably is impossible. That why, it is foolish to try, so
	this is not the goal of this class or module, or even of this library.
	Filtering must be done by Icinga itself, no matter what is done here.

	The first goal of this class is to understand what is done with a filter at a certain level:
	- Which attributes are involved in filtering?
	- What kind of operator is used for which attribute (simple, method, function)?

	The second goal is to create Icinga-compliant filter string using this class:
	- Syntactical correct, but without really looking at semantics
	- Implementing all operators, nesting filters with precedence, using attributes with Attribute objects

	This class implements both nested filters and simple filters. Nested filters are created by passing an operator and
	a list of filter objects as subfilters. Simple filters are created by passing an operator, an attribute and a value.

	:param operator: The operator used in this filter.
	:param operands: Operands.
	"""

	#: Regex pattern grouping characters into the following groups:
	#: 0. Opening parenthesis that don't follow an alphanumeric char
	#: 1. Opening parenthesis that follow an alphanumeric char
	#: 2. Closing parenthesis
	#: 3. Any alphanumeric char or . or [ or ]
	#: 4. Everything else that is not space (single commas, or multiple chars of something else)
	_CHAR_GROUPING = re.compile(r"((?<![\w])[(])|((?<=[\w])[(])|(\))|([\w.\[\]]+)|(,|[^\w.\s()]+)")

	def __init__(
				self,
				operator: Operator,  # The operator
				operands: Optional[Iterable[Any]] = None  # Operands for the operator
			):
		#: The operator used for this particular filter
		self.operator = operator
		#: The operands for the operator (including possible Filter and Attribute objects as well as values)
		self.operands = list()
		# Add with correct type
		for operand in operands:
			if isinstance(operand, Operand):
				self.operands.append(operand)
				continue
			try:
				if Operand.possible_attribute(operand):
					self.operands.append(Attribute(operand))
					continue
			except (TypeError, AttributeParsingError):
				pass
			# else
			self.operands.append(ValueOperand(operand))

	@classmethod
	def simple(cls, attribute, operator: Operator, value) -> "Filter":
		"""Creates a filter of the type attribute <operator> value."""
		attribute = Attribute.ensure_type(attribute)
		return cls(operator, (attribute, value))

	# TODO implement simple object-oriented creation of such Filter objects

	@classmethod
	def from_string(cls, string: str) -> "Filter":
		"""Parse string and create filter for it."""
		try:
			return cls._from_list(cls._to_group_split(string))
		except (IndexError, ValueError):
			raise FilterParsingError(f"Failed to parse filter: {string}")

	@classmethod
	def _to_group_split(cls, string: str) -> Sequence:
		"""Create Filter object from character lst, helper method for from_string()."""
		# Split string inot character lst
		groups = cls._CHAR_GROUPING.findall(f"({string})")
		# res contains the filter to return, cur keeps track of the "current" part in view
		cur = res = list()
		# Track cur references (to go up in hierarchy on closing brackets)
		# The last item is a reference to the "parent" of cur
		stack = list()
		for chars in groups:
			if chars[1]:  # (?<=[\w])[(]
				# Previous item was a function or method
				cur[-1] = Operator(cur[-1], Operator.Type.FUNCTION)
			if chars[0] or chars[1]:  # (
				# One step down the hierarchy
				cur.append(list())
				stack.append(cur)  # Remember the parent
				cur = cur[-1]  # Set view to the new child-filter-build-list
			if chars[2]:  # )
				# One step up the hierarchy
				cur = stack.pop()  # cur <= parent of cur
			if chars[3]:  # Alphanumeric, ., [, ]
				cur.append(ValueOperand(chars[3]))

			if chars[4]:  # Other characters -> operator
				try:
					operator = Operator.from_string(chars[4])
					cur.append(operator)
				except KeyError:
					# No such operator...
					cur.append(ValueOperand(chars[4]))

		return res

	@classmethod
	def _from_list(cls, lst: Union[Sequence, Operand, Operator]) -> "Filter":
		"""Iterable of operands/operators/filter/iterables (of these) to one filter object, helper method for f
		rom_string()."""
		# Make sure it's mutable
		if not hasattr(lst, "pop"):
			lst = list(lst)

		# First step: create a list with method/function calls resolved
		prepared = list()
		# Flag whenever
		call = False
		for index, sub in enumerate(lst):
			if call:
				call = False
				# Previous item was call operator, current is the comma-separated parameter list
				parameters = [list()]
				for i, item in enumerate(sub):
					if isinstance(item, ValueOperand) and item.value == ",":
						parameters.append(list())
					# elif hasattr(item, "__iter__"):
					# 	parameters.append(cls._from_list(item))
					else:
						parameters[-1].append(item)
				# Convert to filter when multiple things have been between two commas
				for i, item in enumerate(parameters):
					if len(item) == 1 and not hasattr(item, "__iter__"):
						# Something like a single ValueOperand
						parameters[i] = item[0]
					else:
						parameters[i] = cls._from_list(item)
				if lst[index - 1].type.pos:
					# Method operator: <operand>.<method>(<parameters>)
					operator = prepared.pop(-1)
					obj = prepared.pop(-1)
					prepared.append(cls(operator, (obj, *parameters)))
				else:
					# Function operator: <function>(<parameters>)
					prepared[-1] = cls(prepared[-1], parameters)
				continue

			try:
				if sub.type.call:
					call = True
			except AttributeError:
				pass
			prepared.append(sub)

		lst = prepared
		# Second step: resolve lists recusively
		for i, item in enumerate(lst):
			if isinstance(item, collections.abc.Sequence):
				lst[i] = cls._from_list(item)

		# Third: Handle every other operator
		def min_operator() -> int:
			"""Get index of the item in lst that is the operator with the smallest precedence."""
			m_index, precedence = -1, 0
			for i, item in enumerate(lst):
				try:
					if (item.precedence and not precedence) or item.precedence < precedence:
						m_index, precedence = i, item.precedence
				except AttributeError:
					pass
			return m_index

		while True:
			i = min_operator()
			if i < 0:
				break

			# Found operator with minimum precedence
			operator = lst[i]
			# Found operator in lst -> what kind of operator is it?
			if operator.type.pos:
				# Operator after first operand
				if operator.type.minimum_operands == 1:
					# <operand><operator>
					operand = lst.pop(i - 1)
					lst[i] = cls(operator, (operand,))
				else:
					# <operand1><operator><operand2>
					operand2 = lst.pop(i + 1)
					operand1 = lst.pop(i - 1)
					lst[i-1] = cls(operator, (operand1, operand2))
			else:
				# Operator before operand
				operand = lst.pop(i + 1)
				lst[i] = cls(operator, (operand,))

		if not lst:
			raise FilterParsingError("Empty list")
		elif len(lst) == 1:
			return lst[0]
		else:
			raise FilterParsingError("Something went wrong...")

	def __str__(self):
		"""Returns the appropriate Icinga filter string."""
		string = self.operator.print(*self.operands)
		return string

	@property
	def is_executable(self) -> bool:
		"""Whether this filter can be executed locally."""
		if not self.operator.is_executable:
			return False
		for operand in self.operands:
			try:
				if not operand.is_executable:
					return False
			except AttributeError:
				# TODO and what if the operand is not "readable" (e.g. duration literal)?
				continue
		return True

	def execute(self, item) -> bool:
		"""Execute the filter for the given item, return True if the filter matches.

		# TODO write more about usage and requirements...
		"""
		# TODO implement
