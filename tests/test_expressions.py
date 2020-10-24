# -*- coding: utf-8 -*-
"""
Tests for the expressions module.
"""

import pytest

from icinga2api_py.expressions import *


#: Literals as string and value tuples
LITERALS = (
	('"a"', "a"),
	("1", 1),
	("3m", 180),
	("2ms", 0.002),
	("true", True),
	("false", False),
	("null", None),
	("{{{abc\ndef}}}", "abc\ndef"),
	(" false ", False),
)


LITERAL_IDS = [f"{i}:{t[0]}" for i, t in enumerate(LITERALS)]


@pytest.fixture(scope="function", params=LITERALS, ids=LITERAL_IDS)
def literal_expression(request):
	"""Some LiteralExpression objects."""
	string, value = request.param
	return LiteralExpression(string, value)


def test_literal_expression(literal_expression):
	"""Test LiteralExpression."""
	o = LiteralExpression.from_string(literal_expression.symbol)
	assert o.value == literal_expression.value
	assert o == literal_expression


@pytest.mark.parametrize("string", (
	# Multiline string not allowed in ""
	'"a\nb"',
	# Missing ""
	"abc",
	# Invalid floats
	"1.1.1",
	# Icinga doesn't allow starting floats with a dot
	".1",
	# Invalid for obvious reasons
	"f a l s e",
	"1q",
))
def test_literal_expression_fails(string):
	"""Test LiteralExpression parsing that should fail."""
	with pytest.raises(ExpressionParsingError):
		LiteralExpression.from_string(string)


def test_variable_expression():
	"""Test VariableExpression."""
	# Just test that none of these are raising an exception
	VariableExpression.from_string("a")
	VariableExpression.from_string("a1")
	VariableExpression.from_string("a_123")
	VariableExpression.from_string("_a")
	VariableExpression.from_string("_abc_123_def")


@pytest.mark.parametrize("string", (
	"1", "true", "-f", "ü", "$a"
))
def test_variable_expression_fails(string):
	"""Test invalid variable expressions."""
	with pytest.raises(ExpressionParsingError):
		VariableExpression.from_string(string)


def test_function_expression():
	"""Test function expression (expression with function operator)."""
	name = "a"
	v = VariableExpression(name)
	o = v(1, 2, 3)
	assert isinstance(o, OperatorExpression)
	# Operands are the VariableExpression object and function args
	assert tuple(o.operands) == (v, 1, 2, 3)
	assert o.operator is FUNCTION_CALL_OPERATOR


def test_operator_basics():
	"""Test Operator basics."""
	def func(*args):
		return args

	o = Operator("##", Operator.Type.BINARY, 1, func)
	assert o.symbol == "##"
	assert str(o) == "##"
	assert o.operate is func

	# Registration
	assert o.register() is True
	assert Operator.get("##", False, 1) is o
	assert Operator.get("##", True, 1) == 1
	assert o.register() is True
	# Register returns False if not registered...
	assert Operator("##", Operator.Type.BINARY).register() is False
	# Except when forced
	assert Operator("##", Operator.Type.BINARY).register(force=True) is True

	assert o.operate(0, 1, 2) == (0, 1, 2)

	assert o == Operator("##", Operator.Type.BINARY, 1, func)
	assert o != 1


@pytest.mark.parametrize("string, args, res", (
		# Binary
		("<", (0, 1), True), ("<", (1, 0), False),
		("<=", (0, 1), True), ("<=", (1, 0), False),
		("==", (0, 0), True), ("==", (1, 0), False),
		("!=", (0, 1), True), ("!=", (1, 1), False),
		(">=", (1, 0), True), (">=", (0, 1), False),
		(">", (1, 0), True), (">", (0, 1), False),
		("&&", (1, 1, 1), True), ("&&", (1, 0, 1), False),
		("||", (1, 0, 0), True), ("||", (0, 0, 0), False),
		# Arithmetic
		("+", (1, 2), 3),
		("-", (3, 2), 1), ("-", (2, 3), -1),
		("*", (2, 3), 6),
		("/", (6, 4), 1.5),
		# Ternary
		("?", (True, 2, 3), 2), ("?", (False, 2, 3), 3),
))
def test_operators_concrete(string, args, res):
	"""Test concrete operators."""
	assert Operator.get(string, False).operate(*args) == res


@pytest.mark.parametrize("string, operand, res", (
		# Unary
		("!", False, True), ("!", True, False),
		("-", 1, -1), ("-", -2, 2),
		("+", 1, 1), ("+", 2, 2),
))
def test_operators_concrete_unary(string, operand, res):
	"""Test unary operators."""
	assert Operator.get(string, True).operate(operand) == res


@pytest.mark.parametrize("operator, string, too_less, too_much", (
		(Operator("$", Operator.Type.UNARY), "$0", 0, 2),
		(Operator("$", Operator.Type.BINARY), "0$1", 1, 3),
		(Operator("§$", Operator.Type.TERNARY), "0§1$2", 2, 4),
), ids=[str(i) for i in range(3)])
def test_operator_print(operator, string, too_less, too_much):
	"""Test that operator raises TypeError with too less or too much operands."""
	right = list(range(too_less + 1))
	too_less = list(range(too_less))
	too_much = list(range(too_much)) if too_much > 0 else None

	assert operator.print(*right).replace(" ", "") == string.replace(" ", "")

	with pytest.raises(TypeError):
		_ = operator.print(*too_less)

	if too_much:
		with pytest.raises(TypeError):
			_ = operator.print(*too_much)


@pytest.mark.parametrize("operator", (
	Operator.get("[", False), Operator.get(".", False),
))
def test_operator_indexer(operator):
	"""Test the "indexer" operators."""
	d = {1: 2, 3: 4, 5: 6}
	a = [7, 8, 9]

	assert operator.operate(a, 0) == 7
	assert operator.operate(d, 1) == 2

	with pytest.raises(ExpressionEvaluationError):
		_ = operator.operate(a, 3)

	with pytest.raises(ExpressionEvaluationError):
		_ = operator.operate(d, 0)

	# Test print
	string = operator.print(1, 2)
	assert string in {"1.2", "1[2]"}

	with pytest.raises(TypeError):
		_ = operator.print(1)  # Too less operands

	with pytest.raises(TypeError):
		_ = operator.print(1, 2, 3)


# TODO add Expression basics test


@pytest.mark.parametrize("string, cls", (
		# One variable
		("a", VariableExpression),
		# One Literal
		("1", LiteralExpression),
		("true", LiteralExpression),
		('"s"', LiteralExpression),
		("4m", LiteralExpression),
))
def test_parsing_simple(string, cls):
	"""Test parsing very simple expressions."""
	o = Expression.from_string(string)
	assert isinstance(o, cls)
	# Check that the subclass's from_string returns the same type
	assert type(getattr(cls, "from_string")(string)) is cls


@pytest.mark.parametrize("string", (
	"", "$", "1q", ",",
	"1, 2, 3",
	# Missing brackets
	"[, 1]", "[1", "1]", "a[]",
	"(1 == 2", "1 == 2)",
	# Missing comma
	"[1, 2 3]", "fun(1 2, 3)"
	# Missing operands
	"1 ==", "== 1", "a and", "and b",
	# More complex...
	"fun(a.b==0, $a)",
	"fun((a.b==0, 1)",
	"fun(a.b==0), 1)",
	"fun(a.b==0,, 1)",
))
def test_parsing_fails(string):
	"""Test parsing invalid expressions."""
	with pytest.raises(ExpressionParsingError):
		Expression.from_string(string)


@pytest.mark.parametrize("string1, string2", (
		('a.b=="a.b"', 'a.b=="a.b"'),
		("1+2*3", "1+(2*3)"),
		("a.b.c==1", "(a.b).c==1"),
		("a.b==1", "(a.b)==(1)"),
		("a.b(1)", "(a.b(1))"),
		("fun(a.b==0, 1)", "fun((a.b==0), 1)"),
		("!a.b && c.d", "(!(a.b))&&(c.d)"),
		("fun1(1, fun2(2, 3))", "(fun1(1, (fun2(2, 3))))"),
		("a.b(1, 2, fun(c, 3))==4", "(a.b(1, 2, (fun(c, 3))))==4"),
		("a.b.c(0)", "(a.b.c)(0)"),
		("a==0 && b==1 && c==2", "((a==0)&&(b==1))&&(c==2)"),
		(
				"a.b==c.d ||(e.f.g(hi,j)&&kl(m.n,!o.p,q.r)&&s.t)||u.v<1||s==\"s\"",
				"(a.b==c.d)||(e.f.g(hi,j)&&kl(m.n,!o.p,q.r)&&s.t)||(u.v<1)||(s==\"s\")"
		),
		("[5, 6, 7][1] == 6", "([5, 6, 7])[1] == 6"),
		("a.b[0]==0", "(a.b)[0]==0"),
))
def test_parsing_complex(string1, string2):
	"""Test parsing and printing more complex expressions."""
	obj1 = Expression.from_string(string1)
	obj2 = Expression.from_string(string2)
	# Spacing is allowed to be different
	assert str(obj1).replace(" ", "") == str(obj2).replace(" ", "")


# Maximum test expression for deep inspection
MAXI_TEST_EXPRESSION = """
(
	0 != 1 && (a == "b" || c*2 < 3d && e["f"] == {{{g
h}}} && i > j || k.l["m"][ n/4+5 ].o["p"] == 6.7)
)
&& 
(
	(
		[+8, ][0] > [-9][0] 
		&& (true && !false)
	)
	&& q(r) == s(10, t, u)
)
"""


def test_parsing_maxi():
	"""Test parsing the maximum string and inspect depply whether that worked."""
	e = Expression.from_string(MAXI_TEST_EXPRESSION)

	def getter(*path):
		"""Helper function to get a sepcific operand."""
		temp = e
		for element in path:
			temp = temp.operands[element]
		return temp

	# Test structure of the expression ==============================
	# 0 != 1 ........................................................
	o = getter(0, 0)
	assert o.operator == Operator.get("!=", False)
	assert o.operands[0].evaluate(None) == 0
	assert o.evaluate(None) is True
	# a == "b" || c*2 < 3d && e["f"] == {{{g\nh}}}
	o = getter(0, 1, 0)
	assert o.operator == BuiltinOperator.AND  # OR bind tighter
	# {{{g\nh}}}
	o = getter(0, 1, 0, 1, 1)
	assert o.evaluate(None) == "g\nh"
	# a == "b" || c*2 < 3d ..........................................
	o = getter(0, 1, 0, 0)
	assert o.operator == BuiltinOperator.OR
	# c*2 < 3d ......................................................
	o = getter(0, 1, 0, 0, 1)
	assert o.operator == BuiltinOperator.LT
	assert o.operands[1].evaluate(None) == 3 * 24 * 60 * 60
	# i > j || k.l["m"][ n/4+5 ].o["p"] == 6.7
	o = getter(0, 1, 1)
	assert o.operator == BuiltinOperator.OR
	# k.l["m"][ n/4+5 ].o["p"]
	o = getter(0, 1, 1, 1, 0)
	assert o.operator == Indexer.SUBSCRIPT
	assert o.operands[1] == LiteralExpression('"p"', "p")
	# k.l["m"][ n/4+5 ].o
	o = getter(0, 1, 1, 1, 0, 0)
	assert o.operator == Indexer.INDEX
	# n/4+5
	o = getter(0, 1, 1, 1, 0, 0, 0, 1)
	assert o.evaluate({"n": 8}) == 7
	# k.l["m"][ n/4+5 ]
	o = getter(0, 1, 1, 1, 0, 0, 0)
	assert o.operator == Indexer.SUBSCRIPT
	context = EvaluationContext({"k.l.m": [0, 1, 2, 3, 4, 5, 6, 11], "n": 8})
	assert o.evaluate(context) == 11
	# [+8, ][0]
	o = getter(1, 0, 0, 0)
	assert o.operator == Indexer.SUBSCRIPT
	assert o.evaluate(None) == 8
	# [+8, ]
	o = getter(1, 0, 0, 0, 0)
	assert isinstance(o, Expression)
	assert isinstance(o, collections.abc.Sequence)
	assert o[0].operator == BuiltinOperator.PLUS
	assert list(o.evaluate(None)) == [8.0]
	# [-9][0]
	o = getter(1, 0, 0, 1)
	assert o.operator == Indexer.SUBSCRIPT
	assert o.evaluate(None) == -9
	# true && !false
	o = getter(1, 0, 1)
	assert o.evaluate(None) is True
	assert o.operands[1].evaluate(None) is True
	assert o.operands[1].operator == BuiltinOperator.NOT
	# s(t, u, v)
	o = getter(1, 1, 1)
	assert o.operator is FUNCTION_CALL_OPERATOR
	flag = False

	def fun(t, v, u):
		nonlocal flag
		flag = True
		return t + v - u

	assert o.evaluate({"s": fun, "t": 9, "u": 8}) == 11
	assert flag


@pytest.fixture(scope="function")
def context():
	"""FilterExecutionContext object."""
	o = EvaluationContext(secondary={"s": 9})
	o["double"] = lambda x: x*2
	o["a"] = [0, 1]
	o["d"] = {"b": 2, "c": 3}
	o["d2.b"] = 2
	o["d2.c"] = 3
	o["e"] = 5
	o["z"] = 6
	return o


def test_context(context):
	"""Basic FilterExecutionContext test."""
	assert context["double"](2) == 4
	assert context["e"] == 5
	assert context["d.c"] == 3
	assert context["d2.c"] == 3
	assert context["s"] == 9
	context["z.a"] = 2
	assert context["z.a"] == 2


def test_context_update(context):
	"""Test FilterExecutionContext.update()."""
	context.update({"z.x": {"y.z": 6}})
	assert context["z.x.y.z"] == context["z"]["x"]["y"]["z"] == 6


def test_context_with_secondary(context):
	"""Test FilterExecutionContext.with_secondary()."""
	secondary = {"e": 99, "t": 20}
	obj = context.with_secondary(secondary)
	assert obj["z"] == 6  # Test primary lookup
	assert obj["e"] == 5  # Test that secondary does not override primary
	assert obj["t"] == 20  # Test secondary lookup
	with pytest.raises(KeyError):
		_ = obj["s"]  # Old secondary gone


@pytest.mark.parametrize("string, context, res", (
		# Without context
		('1==1', None, True),
		('1==2', None, False),
		('1=="2"', None, False),
		('1==1 && 2==2', None, True),
		('1==2 && 2==2', None, False),

		# With context
		("a==1", {"a": 1}, True),
		("a==1", {"a": 2}, False),
		("a==1", {"a": "1"}, False),
		('(a.b==1 && b.c=="2") || (c.d==3)', {"a.b": 1, "b.c": "2", "c.d": 0}, True),
		('(a.b==1 && b.c=="2") || (c.d==3)', {"a.b": 0, "b.c": 0, "c.d": 3}, True),
		('(a.b==1 && b.c=="2") || (c.d==3)', {"a.b": 0, "b.c": 0, "c.d": 0}, False),
		('(a.b==1 && b.c=="2") || (c.d==3)', {"a.b": 1, "b.c": 2, "c.d": 0}, False),
))
def test_string_execution(string, context, res):
	"""Test filter string execution."""
	context = EvaluationContext(context)
	expression = Expression.from_string(string)
	assert expression.evaluate(context) == res

