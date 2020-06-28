# -*- coding: utf-8 -*-
"""This module implements parsing of Icinga filters.


"""

import abc
import collections.abc
import enum
from typing import Union, Optional, Any, Sequence, Iterable, Generator, Callable, Mapping, MutableMapping
import operator as op
import re

from .exceptions import FilterParsingError, LiteralExecutionError, FilterExecutionError


__all__ = ["Operator", "Filter", "FilterExecutionContext"]


#: Patterns for Icinga literals + converter callables (or None if not converted)
_LITERAL_PATTERNS = (
	# String literals
	(re.compile(r'".*"'), lambda s: s[1:-1]),
	# Boolean literals
	(re.compile(r"true"), lambda _: True), (re.compile(r"false"), lambda _: False),
	# Null/None
	(re.compile(r"null"), lambda _: None),
	# Dictionary literals (not parsed as an operand)
	(re.compile(r"{.*}"), None),
	# Array literals (not parsed as an operand)
	(re.compile(r"\[.*\]"), None),
	# Number literals (exponents are not mentioned in Icinga docs)
	(re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?"), float),
	# Duration literals
	(re.compile(r"[-+]?((\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?(ms|s|m|h|d)?)+"), None),
)


class Expression(abc.ABC):
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


class ValueOperand(Expression):
	"""Value used for an operation."""
	def __init__(self, value):
		if not isinstance(value, str):
			value = str(value)
		self.value = value

	def execute(self):
		"""Literal execution."""
		for pattern, converter in _LITERAL_PATTERNS:
			if pattern.fullmatch(self.value):
				if converter is not None:
					return converter(self.value)
				break
		raise LiteralExecutionError(f"Unable to execute literal {self.value}")

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
		return self.value

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


class Filter(Expression):
	"""Represents an Icinga filter.

	- Filters have at minimum one operand and one operator
		- It's possible to use filters as operands for more complex filters (usually joined with logical operators)
		- Simple comparative operators compare the values of their two operands (==, !=, <, ...)
		- Unary operators operate (obviously) on one operand (!, ~)
		- Another operation is a method call on an attribute
			- Fully implementing that without using IOM is at least very difficult, if not impossible
			- An implementation that is at least better (not necessarily complete) can be done with IOM
		- Similar to methods, the use of global functions is also allowed, e.g. match, regex, typeof, ...
			- It seems to be possible to add global functions via configuration
			- This seems therefore impossible to fully implement
		- And also there is the possibility that there is no operator at all, in this case it's similar to Python's
			automatic bool() interpretation in if-clauses (e.g. empty strings are False), but also checks whether this
			attribute is defined (True if defined, False if not)
	- Nesting any filters with explicit precedence (using parenthesis) is possible

	Taking these things into account, it is at least *very, very* difficult to implement filters in a way, that this
	library can fully emulate the filtering of Icinga; it propably is impossible. That why, it is foolish to try, so
	this is not the goal of this class or module, or even of this library.
	Filtering must be done by Icinga itself, no matter what is done here.

	The first goal of this class is to understand what is done with a filter at a certain level:

	- The structure of the filter
	- What is an operator, what are its operands

	The second goal is to create Icinga-compliant filter string using this class:

	- Syntactical correct, but without really looking at semantics
	- Implementing all "simple" operators, nesting filters with precedence, using attributes with Attribute objects

	This class implements both nested filters and simple filters. Nested filters are created by passing an operator and
	a list of filter objects as subfilters. Simple filters are created by passing an operator, an attribute and a value.

	:param operator: The operator used in this filter.
	:param operands: Operands.
	"""

	#: Regex pattern grouping characters into the following groups:
	#: 0. Opening parenthesis that don't follow an alphanumeric char
	#: 1. Opening parenthesis that follow an alphanumeric char
	#: 2. Closing parenthesis
	#: 3. Any alphanumeric char or . or [ or ] or "
	#: 4. Everything else that is not space (single commas, or multiple chars of something else)
	_CHAR_GROUPING = re.compile(r"((?<![\w])[(])|((?<=[\w])[(])|(\))|([\w.\[\]\"]+)|(,|[^\w.\s()\[\]\"]+)")

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
			if isinstance(operand, Expression):
				self.operands.append(operand)
			else:
				self.operands.append(ValueOperand(operand))

	@classmethod
	def simple(cls, expression: Expression, operator: Operator, value) -> "Filter":
		"""Creates a filter of the type <expression> <operator> value, e.g. "a=1"."""
		return cls(operator, (expression, value))

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
	def _from_list(cls, lst: Union[Sequence, Expression, Operator]) -> "Filter":
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

	def execute(self, context: "FilterExecutionContext") -> bool:
		"""Execute the filter for the given item, return True if the filter matches.

		Execution may or may not succeed, depending on operator and operands of this filter and on the lookup context.
		The lookup context is used, whenever a non-filter operand turned out to be not executable locally.
		"""
		# TODO implement recognizing attributes for lookup
		# TODO refactor this code...
		operands = list()
		for operand in self.operands:
			try:
				if isinstance(operand, Filter):
					operands.append(operand.execute(context))
				else:
					operands.append(operand.execute())
			except (AttributeError, LiteralExecutionError):
				if isinstance(operand, Filter):
					raise FilterExecutionError("Unable to execute filter")
				try:
					operands.append(context[operand])
				except KeyError:
					raise FilterExecutionError("Unable to interpret operand, and context lookup failed.")
		try:
			return self.operator.operate(*operands)
		except TypeError:
			raise FilterExecutionError("Operator not executable")

	def execute_many(self, context: Optional["FilterExecutionContext"] = None) -> Callable[[Mapping], bool]:
		"""Get a filter function to execute this filter for many items.

		This method was introduced for use of the returned callable in a Python filter statement as a filter function.
		The context given here is expected to only have a primary context, and the objects for which the filter function
		is applied are used as the secondary context.
		:meth:`execute` is used for filter execution with the resulting context.
		"""
		def execute(mapping) -> bool:
			"""Execute a filter function."""
			return self.execute(context.with_secondary(mapping))

		return execute


class FilterExecutionContext(collections.abc.MutableMapping):
	"""A context looking up variables/constants/functions etc. needed for filter execution.

	Set and lookup of keys can use the dot-syntax to address values of sub-mappings (mappings as values).

	The context is split into a primary and a secondary lookup dictionary.
	The context methods allow modification of individual parts of the primary dict, but the secondary dict can only be
	modified as a whole via the :attr:`secondary` property. The secondary is not modified within this class, it's only
	used for lookup. Note however, that the lookup expects the secondary dict to have mappings as values when the
	dot-syntax is used for lookup, but this class won't ensure that the secondary dict has this structure.
	On lookup the primary dict has precedence.
	"""

	def __init__(self, primary: Optional[Mapping] = None, secondary: Optional[Mapping] = None):
		self._primary = dict()
		if primary:
			self.update(primary)
		self._secondary = secondary or dict()

	def update(self, mapping: Mapping, **kwargs) -> None:
		"""Update the primary lookup dictionary with a key-value mapping.

		This method takes care of splitting keys on dots, also recursively for mapping-values.
		"""
		for key, value in mapping.items():
			mapping, key = self._split_helper(self._primary, key, new=True, override=True)
			self._update(mapping, key, value)

	def _update(self, base: MutableMapping, key, update):
		"""Update base mapping with update for key."""
		if not isinstance(update, collections.abc.Mapping):
			# Set value for key and
			base[key] = update
			return

		base[key] = dict()
		for subkey, value in update.items():
			mapping, subkey = self._split_helper(base[key], subkey, new=True, override=True)
			self._update(mapping, subkey, value)

	@property
	def secondary(self):
		"""Secondary lookup dict."""
		return self._secondary

	@secondary.setter
	def secondary(self, secondary: Mapping):
		"""Set the secondary lookup dict, which is not modified within this class."""
		self._secondary = secondary

	def with_secondary(self, secondary: Mapping) -> "FilterExecutionContext":
		"""Return a new FilterExecutionContext with the existing primary and the given secondary.

		Note that the used primary lookup dict is exactly the same, it's not copied!
		"""
		obj = self.__class__()
		obj._primary = self._primary
		obj._secondary = secondary
		return obj

	@staticmethod
	def _split_helper(mapping, key, new=False, override=False):
		"""Helper for dot-syntax accessing of a mapping, optionally creates new sub-mappings."""
		# TODO something like this is not only used in this module, so maybe move it to somewhere else
		if new and override:
			def get():
				mapping[subkey] = dict()
				return mapping[subkey]
		elif new:
			def get():
				return mapping.setdefault(subkey, dict())
		else:
			def get():
				return mapping[subkey]

		key = key.split(".")
		for subkey in key[:-1]:
			mapping = get()
		return mapping, key[-1]

	def __getitem__(self, key):
		"""Lookup an item in this context."""
		key = str(key)
		try:
			mapping, last = self._split_helper(self._primary, key)
			return mapping[last]
		except (KeyError, TypeError):
			try:
				mapping, last = self._split_helper(self._secondary, key)
				return mapping[last]
			except (KeyError, TypeError):
				raise KeyError(f"Unable to find key {key} in context")

	def __setitem__(self, key, value):
		"""Set context lookup entry key to value, adds if doesn't exist."""
		mapping, key = self._split_helper(self._primary, str(key), new=True, override=True)
		mapping[key] = value

	def __delitem__(self, key):
		"""Delete one item."""
		try:
			mapping, last = self._split_helper(self._primary, key)
			del mapping[key]
		except (KeyError, TypeError):
			raise KeyError(f"No key {key} in context")

	def __len__(self) -> int:
		"""Returns a number for the length of the lookup dicts; but this is not the total number of their items."""
		return len(self._primary) + len(self._secondary)

	def __iter__(self):
		"""A generator yielding all primary and secondary base items."""
		yield from self._primary
		yield from self._secondary
