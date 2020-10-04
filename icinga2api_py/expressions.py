# -*- coding: utf-8 -*-
"""This module implements parsing of Icinga filters.

Written with a glance on https://github.com/Icinga/icinga2/blob/master/lib/config/expression.hpp
and https://github.com/Icinga/icinga2/blob/master/lib/config/expression.cpp

Expressions can come very different:
	- Expressions can be joined to more complex expressions, usually with a logical operator
	- Simple comparative operators compare the values of their two operands (==, !=, <, ...)
	- Unary operators operate (obviously) on one operand (!, ~)
	- Another operation is a method call on an attribute
		- Fully implementing that without using IOM is at least very difficult, if not impossible
		- An implementation that is at least better (not necessarily complete) can be done with IOM
	- Similar to methods, the use of global functions is also allowed, e.g. match, regex, typeof, ...
		- It is possible to add global functions via configuration
		- This seems therefore impossible to fully implement
	- And also there is the possibility that there is no operator at all, in this case it's similar to Python's
		automatic bool() interpretation in if-clauses (e.g. empty strings are False), but also checks whether this
		attribute is defined (True if defined, False if not)
- Nesting any filters with explicit precedence (using parenthesis) is possible

Taking these things into account, it is at least *very, very* difficult to implement expressions in a way, that
this library can fully emulate the expressions of Icinga; it's propably impossible. That why, it is foolish to try, so
this is not the goal of this class or module, or even of this library.
The real stuff must be done by Icinga itself, no matter what is implemented here.

This library mainly only cares of "filters" anyway. A filter is an expression that at least evaluates to one literal,
that can be used in a boolean context. The evaluation can/should use attributes of an object, so that the filter can
evaluate to different results for different objects. However this is not mandatory, a filter could also always evaluate
to True or False without taking object attributes into account.

The first goal of this module is to understand what is done with a filter at a certain level:

- The structure of the filter
- What is an operator, what are its operands
- Evaluate filters that only use "simple" operators
	- There is no definition of "simple"
	- And, or, == and != are definitely simple

The second goal is to create Icinga-compliant filter strings in an OOP-manner

- Syntactical correct, but without really looking at semantics
- Implementing all "simple" operators, nesting filters with precedence, using attributes with Attribute objects

This class implements both nested filters and simple filters. Both are created by passing an operator and its
operands. The operands can be Expression objects (e.g. Filter objects) themselves, or values.

The following things are currently not implemented and have no note to get implemented:
- Assignment, definition of objects/variables/functions/..., mutability in general
- Reference/Dereference operations (&/*)
- Bit operation (Bit-Or/And/XOR, ..., Shifting, ...)
- In / not in Operator
- Dictionary expressions
- Conditional expressions (incl. lambda)
- Loops
- Imports, Exceptions, Apply rules, namespaces, Library expression, Include expression, Try-except expression
"""

import abc
import collections.abc
import enum
import itertools
from typing import Union, Optional, Any, Sequence, Iterable, Generator, Callable, Mapping, MutableMapping, List
import operator as op
import re

from .exceptions import ExpressionParsingError, ExpressionEvaluationError


#######################################################################################################################
# Helper functions used later
#######################################################################################################################

#: Suffixes of duration literals to factors
DURATION_LITERAL_SUFFIXES = {
	"ms": 0.001,
	"s": 1,
	"m": 60,
	"h": 3600,
	"d": 86400,
}


def parse_duration_literal(string: str) -> float:
	"""Duration literal as string to float."""
	num, suffix = re.findall(r"([\d.]+)([a-z]*)", string)[0]
	try:
		return float(num) * DURATION_LITERAL_SUFFIXES[suffix]
	except ValueError:
		raise ExpressionParsingError(f"Unable to parse float in duration literal {string}")
	except KeyError:
		raise ExpressionParsingError(f"Unknown duration suffix {suffix}")


#######################################################################################################################
# Expression class and it's subclasses
#######################################################################################################################


class Expression(abc.ABC):
	"""Abstract expression."""

	def __init__(self, symbol):
		self.symbol = symbol

	def __str__(self):
		"""Expression to string."""
		return self.symbol

	@abc.abstractmethod
	def evaluate(self, context: Mapping):
		raise ExpressionEvaluationError()

	def evaluate_many(self, context: Optional["FilterExecutionContext"] = None) -> Callable[[Mapping], bool]:
		"""Get a filter function to execute this filter for many items.

		This method was introduced for use of the returned callable in a Python filter statement as a filter function.
		The context given here is expected to only have a primary context, and the objects for which the filter function
		is applied are used as the secondary context.
		:meth:`evaluate` is used for expression evaluation with the resulting context.
		"""
		def evaluate(mapping) -> bool:
			"""Execute a filter function."""
			return self.evaluate(context.with_secondary(mapping))

		return evaluate

	@classmethod
	def from_string(cls, string):
		"""Construct such an expression from a string."""
		ret = expression_from_string(string)
		if not isinstance(ret, cls):
			raise ExpressionParsingError(f"Wrong type ({type(ret)} instead of {cls.__name__})")
		return ret

	def __eq__(self, other) -> "OperatorExpression":
		return self.comparison(BuiltinOperator.EQ, other)

	def __ne__(self, other) -> "OperatorExpression":
		return self.comparison(BuiltinOperator.NE, other)

	def __lt__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.comparison(BuiltinOperator.LT, other)

	def __le__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.comparison(BuiltinOperator.LE, other)

	def __ge__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.comparison(BuiltinOperator.GE, other)

	def __gt__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.comparison(BuiltinOperator.GT, other)

	def comparison(self, operator: "Operator", value) -> "OperatorExpression":
		# TODO think about this...
		if isinstance(value, Expression):
			return OperatorExpression(operator, self, value)
		return NotImplemented


class LiteralExpression(Expression):
	"""A simple literal."""

	#: Every convertable simple literal
	_LITERAL_PATTERNS = (
		# Boolean literals
		(re.compile(r"true"), lambda _: True),
		(re.compile(r"false"), lambda _: False),
		# Null/None
		(re.compile(r"null"), lambda _: None),
		# Exponents are not metioned in the Icinga docs... # TODO test (or read source code), what does Icinga do?
		# 	r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?" with exponents
		(re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)"), float),
		# Duration literals  # TODO test if exponents are allowed here
		(re.compile(r"[-+]?((\d+(\.\d*)?|\.\d+)(ms|s|m|h|d)?)+"), parse_duration_literal),
		# String literals
		(re.compile(r'".*"'), lambda string: string[1:-1]),
		(re.compile(r"{{{.*}}}", re.DOTALL), lambda string: string[3:-3]),
	)

	def __init__(self, symbol, value):
		super().__init__(symbol)
		#: Value the literal evaluates to, parsing is done in from_string
		self.value = value

	def evaluate(self, context: Mapping):
		return self.value

	@classmethod
	def from_string(cls, string):
		string = string.strip()
		for pattern, converter in cls._LITERAL_PATTERNS:
			if pattern.fullmatch(string):
				if converter is not None:
					try:
						return cls(string, converter(string))
					except (TypeError, ValueError, AttributeError):
						raise ExpressionParsingError(f"Unable to parse simple literal: {string}")
		raise ExpressionParsingError(f"Unable to parse as simple literal: {string}")

	def comparison(self, operator: "Operator", value) -> Union[bool, "OperatorExpression"]:
		if isinstance(value, self.__class__):
			return operator.operate(self.value, value.value)
		return super().comparison(operator, value)


class VariableExpression(Expression):
	"""A variable in an expression."""

	#: What is valid as a variable here:
	#: Regular variable name with attribute indices and array subscripts
	VALIDATION_PATTERN = re.compile(r"^[a-zA-Z_](\.?[a-zA-Z0-9_]+)*$")

	def __init__(self, symbol):
		super().__init__(symbol)
		self.parts = symbol.split(".")

	def evaluate(self, context: Mapping):
		try:
			temp = context
			for part in self.parts:
				temp = temp[part]
			return temp
		except (KeyError, TypeError):
			raise ExpressionEvaluationError(f"No such symbol in context: {self.symbol}")

	@classmethod
	def from_string(cls, string):
		# Check whether that variable name is generally OK
		if not cls.VALIDATION_PATTERN.match(string):
			raise ExpressionParsingError(f"Invalid variable expression: {string}")
		# Check it's not a literal
		try:
			LiteralExpression.from_string(string)
		except ExpressionParsingError:
			return cls(string)
		else:
			raise ExpressionParsingError(f"Invalid variable expression: {string}")

	def __call__(self, *args) -> "FunctionCallExpression":
		"""Like in Python: Functions behave the same as callable variables."""
		return FunctionCallExpression(self.symbol, *args)

	def __getitem__(self, item):
		"""Array subscript or dictionary indexing."""
		...  # TODO implement


class FunctionCallExpression(VariableExpression):
	"""Function or method call."""

	def __init__(self, symbol, *args):
		super().__init__(symbol)
		self.args = args

	def __str__(self):
		args = (str(arg) for arg in self.args)
		return f"{self.symbol}({', '.join(args)})"

	def evaluate(self, context: Mapping):
		try:
			super().evaluate(context)(*self.args)
		except TypeError:
			raise ExpressionEvaluationError(f"Symbol {self.symbol} is not callable with {len(self.args)} arguments")


class ArrayExpression(Expression):
	"""Array expression (ordered list of values, comma-separated)."""

	def __init__(self, *values):
		super().__init__("")
		self.values = values

	def __str__(self):
		return f"[{', '.join(self.values)}]"

	def evaluate(self, context: Mapping):
		ret = list()
		for val in self.values:
			try:
				ret.append(val.evaluate(context))
			except AttributeError:
				ret.append(val)
		return ret

	def __getitem__(self, item):
		return self.values[item]


class OperatorExpression(Expression):
	"""Represents an expression that consists of at least one operator and one other expression.

	:param operator: The operator used in this filter.
	:param operands: Operands = other expressions as an sequence
	"""

	def __init__(self, operator: "Operator", *operands):
		super().__init__("")
		self.operator = operator
		self.operands = operands

	def __str__(self):
		return self.operator.print(*self.operands)

	def evaluate(self, context: Mapping):
		operands = list()
		for operand in self.operands:
			try:
				operands.append(operand.evaluate(context))
			except ExpressionParsingError:
				raise
			except AttributeError:
				# Pass operand as raw value
				operands.append(operand)
		try:
			return self.operator.operate(*operands)
		except TypeError:
			raise ExpressionEvaluationError("Operator not executable")


#: Pattern for "usual" operators
_USUAL_OPERATOR_PATTERN = re.compile(r"[^\w\s().,[\]]+")


class Operator:
	"""Operator used in filters."""

	class Type(enum.IntEnum):
		"""Type of Operator.

		Each bit has a meaning as follows (in LSBF order):
		1) Whether the operator accepts more than two operands
		2) Whether the operator is written after the first operand
		"""

		#: Unary operators
		UNARY = 0b00
		#: Binary operators (e.g. a==b)
		BINARY = 0b10
		#: Operator accepting operators (e.g. a||b||c)
		MULTARY = 0b11

		@property
		def spaced(self) -> bool:
			"""True if this kind of operator should be separated by spaces."""
			return self is not self.UNARY

		@property
		def pos(self) -> bool:
			"""False if the operator is written before the first operand, True otherwise."""
			return bool(0b10 & self)

		def check_operands_number(self, n) -> int:
			"""Check whether the given number of operands is OK for this operator.

			:return The difference to the expected number of operands (-> 0 means alright)
			"""
			minimum = 1 if self == self.UNARY else 2
			if n - minimum < 0:
				return n - minimum
			if self is self.MULTARY:
				return 0
			needed = 1 if self is self.UNARY else 2
			return n - needed

		@property
		def pattern(self):
			"""Return pattern this operator type is required to match."""
			# Usual operator: no alphanumeric character, no space, no brackets, no dot, no comma
			return _USUAL_OPERATOR_PATTERN

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
		self.precedence = precedence or 99
		#: Function that executes the operation
		self.operate = func

	def register(self, force=False):
		"""Register this operator for translation (used in filter parsing etc.)."""
		# TODO this allows only one operator per symbol... which is not how it works with Icinga
		# 	However this has very low priority
		# 	The way to solve this is distinct the types of the operators, because those can't also be the same
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
				# Yield with or without parenthesis
				if (
						# No parenthesis around simple literals/variables as well as operands that are not expressions
						isinstance(operand, (LiteralExpression, VariableExpression))
						or not isinstance(operand, Expression)
						# No parenthesis if the operand is an OperatorExpression with lower precedence
						or (isinstance(operand, OperatorExpression) and operand.operator.precedence < self.precedence)
				):
					yield string
				else:
					yield f"({string})"

		# Check number of operands
		if self.type.check_operands_number(len(operands)) != 0:
			raise TypeError(f"{self.type.name.title()} operator doesn't allow {len(operands)} operand(s)")
		if self.type.pos:
			if self.type.spaced:
				return f" {self.symbol} ".join(ops())
			else:  # spaced
				return f"{self.symbol}".join(ops())
		else:  # pos
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
	# Simple calculations
	ADD = ("+", Operator.Type.BINARY, 40, op.add)
	SUBTRACT = ("+", Operator.Type.BINARY, 40, op.sub)
	MULIPLY = ("*", Operator.Type.BINARY, 50, op.mul)
	DIVIDE = ("/", Operator.Type.BINARY, 50, op.truediv)
	# Simple comparison
	LT = ("<", Operator.Type.BINARY, 60, op.lt)
	LE = ("<=", Operator.Type.BINARY, 60, op.le)
	EQ = ("==", Operator.Type.BINARY, 60, op.eq)
	NE = ("!=", Operator.Type.BINARY, 60, op.ne)
	GE = (">=", Operator.Type.BINARY, 60, op.ge)
	GT = (">", Operator.Type.BINARY, 60, op.gt)
	# Simple logical operators
	OR = ("||", Operator.Type.MULTARY, 120, (lambda *args: any(args)))
	AND = ("&&", Operator.Type.MULTARY, 130, (lambda *args: all(args)))


def expression_from_string(string: str) -> Expression:
	"""Parse an expression of unknown type from a string."""
	try:
		return _string_to_expression(string)
	except IndexError:
		# Propably a mistake with brackets, because that causes a stack.pop() that may raise IndexError
		raise ExpressionParsingError("Invalid expression, propably a mistake using some kind of brackets")


#: Regex pattern grouping characters into the following groups:
#: 0. Single opening brackets: "(", "["
#: 1. Single closing brackets: ")", "]"
#: 2. A ,
#: 3. A string, starting and ending with " or {{{ resp. }}}
#: 4. Any alphanumeric characters or .
#: 5. Everything else that is not space (multiple chars)
_CHAR_GROUPING = re.compile(
	r"([(\[])|([)\]])|(,)|(\".*?\"|{{{.*?}}})|([\w.]+)|([^()\[\]\"\w.\s]+)",
	# Match line breaks with dots (for multiline strings)
	re.DOTALL
)

#: The intermediate structure produced by _string_to_expression
#: It's a tree-like structure and as such a sequence of the same types and strings as leaves
_STRUCTURE_TYPE = List[Union["_STRUCTURE_TYPE", str]]


def _string_to_expression(string: str) -> Expression:
	"""Parse string to an intermediate structure.

	This method works iteratively.
	"""
	# Opening brackets
	BRACKETS = ("(", "[")
	# Characers that are left untouched in this method (eliminated by helper methods)
	CONTROL_CHARS = (*BRACKETS, ",")

	# Split string into character lst
	groups = _CHAR_GROUPING.findall(string)
	# res contains the structure to return, cur keeps track of the "current" part in view
	cur = res = list()
	# Track cur references (to go up in hierarchy on closing brackets)
	# The last item is a reference to the "parent" of cur
	stack = list()

	for chars in groups:
		if chars[0]:  # Opening brackets of some kind .................................................................
			# One step down the hierarchy
			cur.append(list())
			# Remember the parent
			stack.append(cur)
			# Set view to the new child-filter-build-list
			cur = cur[-1]
			# Remember what kind of bracket caused this
			cur.append(chars[0])
		elif chars[1]:  # Closing brackets of some kind ...............................................................
			temp = cur
			# One step up the hierarchy
			cur = stack.pop()
			# Get what _closing_brackets returns using the predecessor, but take care that there might be no predecessor
			predecessor = (
				cur[-2]
				if len(cur) > 1 and (isinstance(cur[-2], Expression) or cur[-2] not in CONTROL_CHARS)
				else None
			)
			elements = _closing_brackets(predecessor, chars[1], temp)
			# Substitute in cur but not the first element if it's None
			elements = elements[(elements[0] is None):]
			if predecessor is None:
				cur[-1:] = elements
			else:
				cur[-2:] = elements
			pass
		elif chars[2]:  # A comma .....................................................................................
			cur.append(",")
		else:
			# Everything else .............................................................................................
			# The reason to put these into different capturing groups is that they match multiple chars
			# But the different types of characters should get separated
			s = chars[3] or chars[4] or chars[5]
			try:
				# Try to interpret as a literal
				cur.append(LiteralExpression.from_string(s))
				continue
			except ExpressionParsingError:
				# Not a literal -> try as an Operator
				try:
					cur.append(Operator.from_string(s))
					continue
				except KeyError:
					pass
				# Failed to parse as literal and as operator -> that has to be a variable
				cur.append(VariableExpression.from_string(s))

	return _finalise_subexpression(res)


def _closing_brackets(predecessor, bracket: str, lst: Sequence) -> Sequence:
	"""Helper function, called on closing brackets.

	Possible outcomes in this case:
	- Array
	- Function call
	- Sub-expression
	- Array subscript (variable[0])

	:param predecessor: What came before the (opening) bracket, None if nothing
	:param bracket: The closing bracket char
	:param lst: A sequence of expressions, operators and commas inside the brackets

	:return A sequence of things to append instead of predecessor and the brackets
	"""
	opening = lst[0]
	closing = bracket
	lst = lst[1:]
	parens = opening == "("
	if (closing == ")" and opening != "(") or (closing == "]" and opening != "["):
		# Wrong kind
		raise ExpressionParsingError(f"Missing closing brackets for {lst[0]}")

	if len(lst) != 1 or not isinstance(lst[0], Expression):
		# Finalise everything between commas
		values = [(comma, list(values)) for comma, values in itertools.groupby(lst, lambda x: x == ",")]
		values = [
			_finalise_subexpression(sub)
			for comma, sub
			in values
			# Ignore single commas
			if not (comma and len(sub) == 1)
		]
	else:
		values = lst

	if isinstance(predecessor, Expression):
		# Has to be an array subscript or function call
		if parens:
			# Function call
			return predecessor(*values),
		elif not values:
			# Empty array subscript
			raise ExpressionParsingError("Empty array subscription")
		...  # TODO It's an array subscript - how to handle that???
		raise ExpressionParsingError("Currently unable to parse array subscript")
	if parens:
		if values:
			# Return the finalised sub-expression
			return predecessor, values[0]
		else:
			raise ExpressionParsingError("Empty sub-expression")
	else:
		# Array
		return predecessor, ArrayExpression(*values)


def _finalise_subexpression(lst: _STRUCTURE_TYPE) -> Expression:
	"""Helper function: finalise a (sub-)expression -
	this is called with stuff inside closing parenthesis and between commas in an array."""

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

	pass
	while True:
		i = min_operator()
		if i < 0:
			# No operator in lst
			break

		# Operator to consider (lowest precedence)
		operator = lst[i]
		# Found operator in lst -> what kind of operator is it?
		if operator.type.pos:
			# Operator after first operand
			if operator.type is Operator.Type.UNARY:
				# <operand><operator>
				operand = lst.pop(i - 1)
				lst[i] = OperatorExpression(operator, (operand, ))
			else:
				# <operand1><operator><operand2>
				operand2 = lst.pop(i + 1)
				operand1 = lst.pop(i - 1)
				# Join OperatorExpression objects if the operator is the same and accepts more than two operands
				lst[i - 1] = OperatorExpression(operator, operand1, operand2)
		else:
			# Operator before operand
			operand = lst.pop(i + 1)
			lst[i] = OperatorExpression(operator, operand)

	# Return the finalised (sub-)expression
	if not lst:
		raise ExpressionParsingError("Empty sub-expression")
	elif len(lst) == 1:
		return lst[0]
	else:
		raise ExpressionParsingError("Invalid expression: missing operator or comma")


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
