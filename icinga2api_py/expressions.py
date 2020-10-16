# -*- coding: utf-8 -*-
"""This module implements parsing of Icinga filters.

Written with a glance on https://github.com/Icinga/icinga2/blob/master/lib/config/expression.hpp
and https://github.com/Icinga/icinga2/blob/master/lib/config/expression.cpp
as well as https://github.com/Icinga/icinga2/blob/master/lib/config/config_lexer.ll

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
- Comments
"""

import abc
import collections.abc
import enum
import itertools
from typing import Union, Optional, Any, Sequence, Iterable, Generator, Callable, Mapping, MutableMapping, List, Tuple
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


class LiteralExpression(Expression):
	"""A simple literal."""

	#: Every convertable simple literal
	_LITERAL_PATTERNS = (
		# Boolean literals
		(re.compile(r"true"), lambda _: True),
		(re.compile(r"false"), lambda _: False),
		# Null/None
		(re.compile(r"null"), lambda _: None),
		# Icinga does not support exponents as far as I can see
		# 	r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?" with exponents
		(re.compile(r"[0-9]+(\.[0-9]+)?"), float),
		# Duration literals (don't support exponents as well)
		(re.compile(r"[0-9]+(\.[0-9]+)?(ms|s|m|h|d)?"), parse_duration_literal),
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

	def __eq__(self, other):
		try:
			return self.value == other.value
		except AttributeError:
			return NotImplemented


class ArrayExpression(Expression):
	"""Array expression (ordered list of expressions, comma-separated in string representation)."""

	def __init__(self, *values):
		super().__init__("")
		self.values = values

	def __str__(self):
		return f"[{', '.join(str(value) for value in self.values)}]"

	def evaluate(self, context: Mapping):
		ret = list()
		for val in self.values:
			try:
				ret.append(val.evaluate(context))
			except AttributeError:
				ret.append(val)
		return ret

	def __getitem__(self, item):
		return OperatorExpression(Indexer.SUBSCRIPT, self, item)


class _VariableExpressionMixin:
	"""Mixin for expression with a type unknown at parsing time."""

	def __call__(self: Expression, *args) -> "FunctionCallExpression":
		"""Like in Python: Functions behave the same as callable variables."""
		return OperatorExpression(FUNCTION_CALL_OPERATOR, [self, *args])

	def __getitem__(self: Expression, item):
		"""Array subscript or dictionary indexing."""
		return OperatorExpression(Indexer.SUBSCRIPT, self, item)


class VariableExpression(Expression, _VariableExpressionMixin):
	"""A variable in an expression."""

	#: What is valid as a variable here:
	#: Starting with a letter, then alphanumeric characters including unerscore
	VALIDATION_PATTERN = re.compile(r"^[a-zA-Z_]([a-zA-Z0-9_]+)*$")

	def evaluate(self, context: Mapping):
		try:
			return context[self.symbol]
		except KeyError:
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


class OperatorExpression(Expression, _VariableExpressionMixin):
	"""Represents an expression that consists of at least one operator and one other expression.

	:param operator: The operator used in this filter.
	:param operands: Operands = other expressions as an sequence
	"""

	def __init__(self, operator: "Operator", *operands):
		super().__init__("")
		self.operator = operator
		# Check number of operands
		if operator.type.check_operands_number(len(operands)) != 0:
			raise TypeError(f"{operator.type.name.title()} operator doesn't allow {len(operands)} operand(s)")
		self.operands = operands

	def __str__(self):
		return self.operator.print(*self.operands)

	def evaluate(self, context: Mapping):
		# This is done in the Operator class, because evaluation of operands can depend on the operator itself
		return self.operator.evaluate(context, *self.operands)


class Operator:
	"""Operator used in filters."""

	class Type(enum.IntEnum):
		"""Type of Operator."""

		#: Unary operators (e.g. !a)
		UNARY = 0b00
		#: Binary operators (e.g. a==b)
		BINARY = 0b01
		#: Ternary operators (a ? b : c)
		TERNARY = 0b10
		#: Not really one of the others
		MISCELLANEOUS = 0b11

		@property
		def spaced(self) -> bool:
			"""True if this kind of operator should be separated by spaces."""
			return self is not self.UNARY

		@property
		def pos(self) -> bool:
			"""False if the operator is written before the first operand, True otherwise."""
			return self is not self.UNARY

		def check_operands_number(self, n) -> int:
			"""Check whether the given number of operands is OK for this operator.

			:return The difference to the expected number of operands (-> 0 means alright)
			"""
			if self is self.MISCELLANEOUS:
				return 0
			return n - (int(self) + 1)

		@property
		def pattern(self):
			"""Return pattern this operator type is required to match."""
			# Usual operator: no alphanumeric character, no space, no brackets, no dot, no comma
			return re.compile(r"[^\w\s(),]+")

	#: Get an Operator object by a tuple of two things:
	#: 1. Its string representation
	#: 2. A bool whether this is a unary operator
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

	def register(self, force=False) -> bool:
		"""Register this operator for translation (used in filter parsing etc.).

		:param force: True to overwrite previous registrations
		:returns True on success, False otherwise
		"""
		# TODO is should be possible to register an operator like e.g. the function call operator
		# 	(or the ternary operator, in general: an operator with its symbols not together)
		# 	in a way that it can be found later by the parsing finalise function.
		# 	Just taking the first symbol would break operators like <=, so a better solution is needed
		key = (self.symbol, self.type is Operator.Type.UNARY)
		if force:
			self._OPERATOR_TRANSLATION[key] = self
			return True
		return self._OPERATOR_TRANSLATION.setdefault(key, self) is self

	@classmethod
	def get(cls, symbol, unary: bool, default=None):
		"""Get Operator object by symbol and whether it's an unary operator."""
		try:
			return cls._OPERATOR_TRANSLATION[(symbol, unary)]
		except KeyError:
			return default

	@classmethod
	def all_operators(cls) -> Iterable["Operator"]:
		"""Return all operators, sorted by precedence."""
		return sorted((operator for operator in cls._OPERATOR_TRANSLATION.values()), key=op.attrgetter("precedence"))

	def evaluate(self, context: Mapping, *operands):
		"""Evaluate an OperatorExpression.

		The reason why this is not done in the OperatorExpression class, that evaluation of operands can depend on the
		operator.
		"""
		values = list()
		for operand in operands:
			try:
				value = operand.evaluate(context)
				values.append(value)
			except ExpressionParsingError:
				raise
			except AttributeError:
				# Pass operand as raw value
				values.append(operand)
		try:
			return self.operate(*values)
		except TypeError:
			raise ExpressionEvaluationError("Operator not executable, or it does not accept this number of operands")

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

	def operand_strings(self, ops: Iterable) -> Generator[str, None, None]:
		"""Generator yielding operands as strings with or without brackets."""
		for operand in ops:
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

	def print(self, *operands):
		"""Return a string that represents the operation done on the given args."""
		# First check that this print method is able to handle this operator
		if self.type is self.Type.MISCELLANEOUS:
			raise ValueError("For operator of type miscellaneous it's mandatory to overwrite print()")
		# Check number of operands
		if self.type.check_operands_number(len(operands)) != 0:
			raise TypeError(f"{self.type.name.title()} operator doesn't allow {len(operands)} operand(s)")
		if self.type is self.Type.TERNARY:
			a, b, c = self.operand_strings(operands)
			s1, s2 = self.symbol
			return f"{a} {s1} {b} {s2} {c}"
		elif self.type is not self.Type.UNARY:
			if self.type.spaced:
				return f" {self.symbol} ".join(self.operand_strings(operands))
			else:  # spaced
				return f"{self.symbol}".join(self.operand_strings(operands))
		else:  # pos
			# Unary operator: <operator><attribute>
			return f"{self.symbol}{list(self.operand_strings(operands))[0]}"


class BuiltinOperator(Operator, enum.Enum):
	"""Simple operators that build on builtin operators."""

	def __new__(cls, *args):
		return Operator.__new__(cls)

	def __init__(self, *args):
		Operator.__init__(self, *args)
		self.register(True)

	# Simple unary operators
	NOT = ("!", Operator.Type.UNARY, 2, (lambda x: not x))
	MINUS = ("-", Operator.Type.UNARY, 2, (lambda x: -x))
	PLUS = ("+", Operator.Type.UNARY, 2, (lambda x: +x))
	# Simple calculations
	ADD = ("+", Operator.Type.BINARY, 4, op.add)
	SUBTRACT = ("-", Operator.Type.BINARY, 4, op.sub)
	MULIPLY = ("*", Operator.Type.BINARY, 5, op.mul)
	DIVIDE = ("/", Operator.Type.BINARY, 5, op.truediv)
	# Simple comparison
	LT = ("<", Operator.Type.BINARY, 6, op.lt)
	LE = ("<=", Operator.Type.BINARY, 6, op.le)
	EQ = ("==", Operator.Type.BINARY, 6, op.eq)
	NE = ("!=", Operator.Type.BINARY, 6, op.ne)
	GE = (">=", Operator.Type.BINARY, 6, op.ge)
	GT = (">", Operator.Type.BINARY, 6, op.gt)
	# Simple logical operators
	OR = ("||", Operator.Type.BINARY, 12, (lambda *args: any(args)))
	AND = ("&&", Operator.Type.BINARY, 13, (lambda *args: all(args)))
	# Ternary operator
	TERNARY = ("?:", Operator.Type.TERNARY, 16)


class Indexer(Operator, enum.Enum):
	"""Indexer(s) are the operators for subscription and attribute access."""

	def __new__(cls, *args):
		return Operator.__new__(cls)

	def __init__(self, symbol):
		Operator.__init__(self, self.value.format("", ""), Operator.Type.MISCELLANEOUS, 1, self._operate)
		self.register(True)

	SUBSCRIPT = "{}[{}]"
	INDEX = "{}.{}"

	@staticmethod
	def _operate(subscriptable, item):
		try:
			return subscriptable[item]
		except (IndexError, KeyError, TypeError):
			raise ExpressionEvaluationError("Subscript or attribute access failed")

	def evaluate(self, context: Mapping, expression: Expression, item):
		"""Evaluate an indexing operation - this is different from other evaluations."""
		if hasattr(item, "value"):  # LiteralExpresion or similar
			item = item.value
		if not isinstance(item, int):  # Make sure item is either int or str
			item = str(item)

		return self._operate(expression.evaluate(context), item)

	def print(self, *operands):
		if len(operands) != 2:
			raise TypeError(f"Expected 2 operands for index operator, got {len(operands)}")
		return self.value.format(*self.operand_strings(operands))


class FunctionCall(Operator):
	"""Function call operator."""

	def __init__(self):
		# TODO check precedence value in Icinga language reference
		super().__init__("()", Operator.Type.MISCELLANEOUS, 1, self._operate)

	@staticmethod
	def _operate(func, *args):
		try:
			return func(*args)
		except TypeError:
			raise ExpressionEvaluationError(f"Function {func} is not callable with {len(args)} arguments")

	def print(self, *operands):
		return f"{operands[0]}({', '.join(operands[1:])})"


FUNCTION_CALL_OPERATOR = FunctionCall()
FUNCTION_CALL_OPERATOR.register(True)


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
#: 4. Any alphanumeric characters
#: 5. Everything else that is not space (multiple chars)
_CHAR_GROUPING = re.compile(
	r"([(\[])|([)\]])|(,)|(\".*?\"|{{{.*?}}})|([\w]+)|([^()\[\]\"\w\s]+)",
	# Match line breaks with dots (for multiline strings)
	re.DOTALL
)


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
			# Substitute in cur
			cur[-1:] = elements
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
				# Not a literal -> try as an Operator...
				# It's unary if it's not preceeed by an expression
				unary = not (len(cur) and isinstance(cur[-1], Expression))
				operator = Operator.get(s, unary)
				if operator is not None:
					cur.append(operator)
					continue
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
		temp_values = [(comma, list(values)) for comma, values in itertools.groupby(lst, lambda x: x == ",")]
		values = list()
		for i, comma_sub in enumerate(temp_values):
			comma, sub = comma_sub
			if i % 2 == 1:
				# One comma expected
				if not comma:
					raise ExpressionParsingError("Missing comma")
				if len(sub) > 1:
					raise ExpressionParsingError("Unexpected multiple commas")
				continue
			if comma:
				raise ExpressionParsingError("Unexpected comma")
			values.append(_finalise_subexpression(sub))
	else:
		values = lst

	if isinstance(predecessor, Expression):
		try:
			# Has to be an array subscript or function call
			if parens:
				# Function call
				return FUNCTION_CALL_OPERATOR, values
			elif not values:
				# Empty array subscript
				raise ExpressionParsingError("Empty array subscription")
			elif len(values) > 1:
				raise ExpressionParsingError("Invalid array or dictionary subscript")
			# Array subscript
			return Indexer.SUBSCRIPT, values[0]
		except TypeError:
			# Array subscript / function call failed
			raise ExpressionParsingError("Invalid array subscript or function call")
	if parens:
		if values:
			# Return the finalised sub-expression
			return values[0],
		else:
			raise ExpressionParsingError("Empty sub-expression")
	else:
		# Array
		return ArrayExpression(*values),


def _finalise_subexpression(lst: List[Union[Expression, Operator]]) -> Expression:
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

		if operator.type is Operator.Type.UNARY:
			# <operator><operand>
			operand = lst.pop(i + 1)
			lst[i] = OperatorExpression(operator, operand)
		else:
			# <operand1><operator><operand2>
			operand2 = lst.pop(i + 1)
			operand1 = lst.pop(i - 1)
			# Join OperatorExpression objects if the operator is the same and accepts more than two operands
			lst[i - 1] = OperatorExpression(operator, operand1, operand2)

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
