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

	@classmethod
	def from_string(cls, string):
		"""Construct such an expression from a string."""
		ret = expression_from_string(string)
		if not isinstance(ret, cls):
			raise ExpressionParsingError(f"Wrong type ({type(ret)} instead of {cls.__name__})")
		return ret

	def __eq__(self, other) -> "OperatorExpression":
		return self.compose(BuiltinOperator.EQ, other)

	def __ne__(self, other) -> "OperatorExpression":
		return self.compose(BuiltinOperator.NE, other)

	def __lt__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.compose(BuiltinOperator.LT, other)

	def __le__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.compose(BuiltinOperator.LE, other)

	def __ge__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.compose(BuiltinOperator.GE, other)

	def __gt__(self, other) -> "OperatorExpression":
		"""Create a filter comparing this attribute to a value."""
		return self.compose(BuiltinOperator.GT, other)

	def compose(self, operator: "Operator", value) -> "OperatorExpression":
		return OperatorExpression(operator, self, value)


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
		string.strip()
		for pattern, converter in cls._LITERAL_PATTERNS:
			if pattern.fullmatch(string):
				if converter is not None:
					try:
						return converter(string)
					except (TypeError, ValueError, AttributeError):
						raise ExpressionParsingError(f"Unable to parse simple literal: {string}")
		raise ExpressionParsingError(f"Unable to parse as simple literal: {string}")


class VariableExpression(Expression):
	"""A variable in an expression."""

	def evaluate(self, context: Mapping):
		try:
			return context[self.symbol]
		except KeyError:
			raise ExpressionEvaluationError(f"No such symbol in context: {self.symbol}")

	@classmethod
	def from_string(cls, string):
		# TODO check whether that string is a valid variable name
		return cls(string.strip())

	def __call__(self, *args) -> "FunctionCallExpression":
		"""Like in Python: Functions behave the same as callable variables."""
		return FunctionCallExpression(self.symbol, *args)


class FunctionCallExpression(VariableExpression):
	"""Function or method call."""

	def __init__(self, symbol, *args):
		super().__init__(symbol)
		self.args = args

	def __str__(self):
		return f"{self.symbol}({', '.join(self.args)})"

	def evaluate(self, context: Mapping):
		try:
			super().evaluate(context)(*self.args)
		except TypeError:
			raise ExpressionEvaluationError(f"Symbol {self.symbol} is not callable with {len(self.args)} arguments")

	@classmethod
	def from_string(cls, string):
		string = string.strip()
		# String is now: <function symbol>(<arg1>, <arg2>, ...)
		# Get the function symbol
		try:
			symbol, rem = string.split("(", 1)
		except ValueError:
			raise ExpressionParsingError("Missing opening parenthesis for function call")
		# Cut of closing parenthesis
		if rem[-1] != "(":
			raise ExpressionParsingError("Missing closing parenthesis for function call")
		rem = rem[:-1]
		# The problem at this point is, that splitting at commas wouldn't work
		# because an argument could be another function call with comma-separated args
		# Therefore, here is a little trick to make that work:
		# Lets put [] around the args and treat them as an array
		# The ArrayExpression parsing has the same problem in general and should be able to solve it
		array = ArrayExpression.from_string(f"[{rem}]")
		return cls(symbol, array.values)


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

	def __init__(self, operator, *operands):
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


def expression_from_string(string: str) -> Expression:
	"""Parse an expression of unknown type from a string."""
	struct = _string_to_structure(string)
	return _finalise_subexpression(struct)


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

#: The intermediate structure produced by _string_to_structure
#: It's a tree-like structure and as such a sequence of the same types and strings as leaves
_STRUCTURE_TYPE = List[Union["_STRUCTURE_TYPE", str]]


def _string_to_structure(string: str) -> _STRUCTURE_TYPE:
	"""Parse string to an intermediate structure.

	This method works iteratively.
	"""
	# Split string into character lst
	groups = _CHAR_GROUPING.findall(f"({string})")
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
			elements = _closing_brackets((cur.pop(-1) if len(cur) > 0 else None), chars[1], temp)
			# Append to cur but do not append the first element if it's None
			cur.extend(elements[(elements[0] is None):])
		elif chars[2]:  # A comma .....................................................................................
			# Append ellipsis as a placeholder to test for on closing brackets
			cur.append(...)
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
			except KeyError:
				pass
			# Failed to parse as literal and as operator -> that has to be a variable
			cur.append(VariableExpression.from_string(s))

	return res


def _closing_brackets(predecessor, bracket: str, lst: Sequence) -> Sequence:
	"""Helper function, called on closing brackets.

	Possible outcomes in this case:
	- Array
	- Function call
	- Sub-expression
	- Array subscript (variable[0])

	:param predecessor: What came before the (opening) bracket, None if nothing
	:param bracket: The closing bracket char
	:param lst: A sequence of expressions, operators and commas (as ellipsis) inside the brackets

	:return A sequence of things to append instead of predecessor and the brackets
	"""
	opening = lst[0]
	closing = bracket
	lst = lst[1:]
	parens = opening == "("
	if (closing == ")" and opening != "(") or (closing == "]" and opening != "["):
		# Wrong kind
		raise ExpressionParsingError(f"Missing closing brackets for {lst[0]}")

	# Finalise everything between commas
	values = ((comma, list(values)) for comma, values in itertools.groupby(lst, lambda x: x is ...))
	values = [
		_finalise_subexpression(sub)
		for comma, sub
		in values
		# Ignore single commas
		if not (comma and len(sub) == 1)
	]

	if len(values) == 1:
		# It was a comma-separated list of values
		if parens:
			# Function call
			return predecessor(*values),
		else:
			# Array
			return ArrayExpression(*values),
	# Not a comma-separated list -> sub-expression or array subscript or array with one item
	if parens:
		# Return the finalised subexpression
		return predecessor, values[0] if predecessor else values[0],
	else:
		# It's inside [], so it's an array with one item or an array subscript...
		if isinstance(predecessor, Expression):
			...  # TODO It's an array subscript - how to handle that???
			raise ExpressionParsingError("Currently unable to parse array subscript")
		# Array with one value
		return predecessor, ArrayExpression(values[0])


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
			if operator.type.minimum_operands == 1:
				# <operand><operator>
				operand = lst.pop(i - 1)
				lst[i] = OperatorExpression(operator, (operand, ))
			else:
				# <operand1><operator><operand2>
				operand2 = lst.pop(i + 1)
				operand1 = lst.pop(i - 1)
				# TODO join OperatorExpression objects if the operator is the same and accepts more than two operands
				lst[i - 1] = OperatorExpression(operator, (operand1, operand2))
		else:
			# Operator before operand
			operand = lst.pop(i + 1)
			lst[i] = OperatorExpression(operator, (operand, ))

	# Return the finalised (sub-)expression
	if not lst:
		raise ExpressionParsingError("Empty list")
	elif len(lst) == 1:
		return lst[0]
	else:
		print(lst)
		raise ExpressionParsingError("Something went wrong: finalising expression wasn't able to finalise...")


#######################################################################################################################
# Old code
# TODO remove this as soon as the new code covers all of the old one's functionality and has tests
#######################################################################################################################


#: Patterns for Icinga literals + converter callables (or None if not converted)
_LITERAL_PATTERNS = (
	# String literals
	(re.compile(r'".*"'), lambda s: s[1:-1]),
	# Boolean literals
	# TODO A problem of this approach here (in general) is, that Python's True/False are not converted to Icinga's bool
	# 	values correctly (because of lowercase)
	(re.compile(r"true"), lambda _: True), (re.compile(r"false"), lambda _: False),
	# Null/None
	(re.compile(r"null"), lambda _: None),
	# Dictionary literals (not parsed as an operand)
	(re.compile(r"{.*}"), None),
	# Array literals (not parsed as an operand)
	(re.compile(r"\[.*\]"), None),
	# Number literals (exponents are not mentioned in Icinga docs)
	# Exponents are not metioned in the Icinga docs... # TODO test (or read source code), what does Icinga do?
	# 	r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?" with exponents
	(re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)"), float),
	# Duration literals
	# TODO interpret duration literals, it's not that difficult...
	(re.compile(r"[-+]?((\d+(\.\d*)?|\.\d+)(ms|s|m|h|d)?)+"), None),
)


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
		raise ExpressionEvaluationError(f"Unable to execute literal {self.value}")

	def __str__(self):
		return self.value

	def __repr__(self):
		return f"<{self.__class__.__name__} {repr(self.value)}>"

	def __eq__(self, other):
		try:
			return self.value == other.value
		except AttributeError:
			return self.compose(BuiltinOperator.EQ, other)

	def __ne__(self, other):
		try:
			return self.value != other.value
		except AttributeError:
			return self.compose(BuiltinOperator.NE, other)


#: Pattern for "usual" operators
_USUAL_OPERATOR_PATTERN = re.compile(r"[a-zA-Z_][\w_]*")
#: Pattern for functions and methods
_FUNCTION_PATTERN = re.compile(r"[^\w\s().,[\]]+")


class Operator:
	"""Operator used in filters."""

	class Type(enum.IntEnum):
		"""Type of Operator.

		Each bit has a meaning as follows (in LSBF order):
		1) Whether the operator should (but not neccesarily must) be separated by spaces
		2) Whether the operator is written after the first operand
		3) Whether the operator is some type of function call
		"""

		#: Unary operators
		UNARY = 0b000
		#: Comparative operators (e.g. a==b)
		COMPARISON = 0b010
		#: Non-unary logical operators (e.g. a||b)
		LOGICAL = 0b011
		#: Function (e.g. len(a))
		FUNCTION = 0b100
		#: Method (executed *on* an attribute, not with; e.g. dict.contains(e))
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
			- It is possible to add global functions via configuration
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

	The second goal is to create Icinga-compliant filter strings using this class:

	- Syntactical correct, but without really looking at semantics
	- Implementing all "simple" operators, nesting filters with precedence, using attributes with Attribute objects

	This class implements both nested filters and simple filters. Both are created by passing an operator and its
	operands. The operands can be Expression objects (e.g. Filter objects) themselves, or values.

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
			raise ExpressionParsingError(f"Failed to parse filter: {string}")

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
			raise ExpressionParsingError("Empty list")
		elif len(lst) == 1:
			return lst[0]
		else:
			raise ExpressionParsingError("Something went wrong...")

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
			except (AttributeError, ExpressionEvaluationError):
				if isinstance(operand, Filter):
					raise ExpressionEvaluationError("Unable to execute filter")
				try:
					operands.append(context[operand])
				except KeyError:
					raise ExpressionEvaluationError("Unable to interpret operand, and context lookup failed.")
		try:
			return self.operator.operate(*operands)
		except TypeError:
			raise ExpressionEvaluationError("Operator not executable")

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
