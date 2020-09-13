# -*- coding: utf-8 -*-
"""
Tests for the expressions module.
"""

import pytest

from icinga2api_py.expressions import ValueOperand, Operator, Filter, FilterExecutionContext


@pytest.mark.parametrize("value, res, executed", (
		('"a"', None, "a"),
		("1", None, 1),
		(1, "1", 1),
		(.1, "0.1", .1),
		(".1", None, .1),
		("true", None, True),
		("false", None, False),
		("null", None, None),
))
def test_value_operand(value, res, executed):
	"""Test ValueOperand."""
	o = ValueOperand(value)
	res = res or value
	assert o.value == res

	assert o.execute() == executed


def test_operator_basics():
	"""Test Operator basics."""
	def func(*args):
		return args

	o = Operator("##", Operator.Type.COMPARISON, 1, func)
	assert o.symbol == "##"
	assert str(o) == "##"
	assert o.operate is func

	# Registration
	assert o.register() is True
	assert Operator.from_string("##") is o
	assert o.register() is True
	# Register returns False if not registered...
	assert Operator("##", Operator.Type.COMPARISON).register() is False
	# Except when forced
	assert Operator("##", Operator.Type.COMPARISON).register(force=True) is True

	assert o.operate(0, 1, 2) == (0, 1, 2)

	assert o == Operator("##", Operator.Type.COMPARISON, 1, func)
	assert o != 1


@pytest.mark.parametrize("string, args, res", (
		("<", (0, 1), True), ("<", (1, 0), False),
		("<=", (0, 1), True), ("<=", (1, 0), False),
		("==", (0, 0), True), ("==", (1, 0), False),
		("!=", (0, 1), True), ("!=", (1, 1), False),
		(">=", (1, 0), True), (">=", (0, 1), False),
		(">", (1, 0), True), (">", (0, 1), False),
		("&&", (1, 1, 1), True), ("&&", (1, 0, 1), False),
		("||", (1, 0, 0), True), ("||", (0, 0, 0), False),
))
def test_operators_concrete(string, args, res):
	"""Test concrete operators."""
	assert Operator.from_string(string).operate(*args) == res


def test_operator_print_unary():
	"""Test Operator.print() for unary operator type."""
	with pytest.raises(ValueError):
		_ = Operator("a", Operator.Type.UNARY)  # Would be indistuingishable from the operand

	op = Operator("+", Operator.Type.UNARY)
	assert op.print(1) == "+1"

	with pytest.raises(TypeError):
		_ = op.print(1, 2)  # Too many operands


def test_operator_print_comparison():
	"""Test Operator.print() for comparison operator type."""
	with pytest.raises(ValueError):
		_ = Operator("a", Operator.Type.UNARY)  # Would be indistuingishable from the operand

	op = Operator("+", Operator.Type.COMPARISON)
	assert op.print(1, 2).replace(" ", "") == "1+2"

	with pytest.raises(TypeError):
		_ = op.print(1)  # Too less operands


def test_operator_print_logical():
	"""Test Operator.print() for logical operator type."""
	with pytest.raises(ValueError):
		_ = Operator("a", Operator.Type.LOGICAL)  # Would be indistuingishable from the operand

	op = Operator("+", Operator.Type.LOGICAL)
	assert op.print(1, 2).replace(" ", "") == "1+2"

	with pytest.raises(TypeError):
		_ = op.print(1)  # Too less operands


def test_operator_print_function():
	"""Test Operator.print() for function operator type."""
	with pytest.raises(ValueError):
		_ = Operator("+", Operator.Type.FUNCTION)  # Function name needs to consist of alphanumerical characters

	op = Operator("a", Operator.Type.FUNCTION)
	assert op.print("b") == "a(b)"


def test_operator_print_method():
	"""Test Operator.print() for method operator type."""
	with pytest.raises(ValueError):
		_ = Operator("+", Operator.Type.METHOD)  # Function name needs to consist of alphanumerical characters

	op = Operator("a", Operator.Type.METHOD)
	assert op.print("b") == "b.a()"


# TODO add filter basics test

# TODO add filter to str test

@pytest.mark.parametrize("string, string2", (
		('a.b=="a.b"', 'a.b=="a.b"'),
		("a.b==1", "(a.b)==(1)"),
		("a.b(1)", "(a.b(1))"),
		("fun(a.b==0, 1)", "fun((a.b==0), 1)"),
		("!a.b && c.d", "(!(a.b))&&(c.d)"),
		("fun1(1, fun2(2, 3))", "(fun1(1, (fun2(2, 3))))"),
		("a.b(1, 2, fun(c, 3))==4", "(a.b(1, 2, (fun(c, 3))))==4"),
		("a==0 && b==1 && c==2", "((a==0)&&(b==1))&&(c==2)"),
		# Maxi test string...
		(
				"a.b==c.d ||(e.f.g(hi,j)&&kl(m.n,!o.p,q.r)&&s.t)||u.v<1",
				"(a.b==c.d)||(e.f.g(hi,j)&&kl(m.n,!o.p,q.r)&&s.t)||(u.v<1)"
		)
))
def test_filter_fromstring(string, string2):
	"""Test Filter.form_string()."""
	obj = Filter.from_string(string)
	obj2 = Filter.from_string(string2)
	fstring = str(obj).replace(" ", "")
	# Spacing is allowed to be different
	assert fstring == string.replace(" ", "")
	assert str(obj2).replace(" ", "") == fstring


@pytest.fixture(scope="function")
def context():
	"""FilterExecutionContext object."""
	o = FilterExecutionContext(secondary={"s": 9})
	o["double"] = lambda x: x*2
	o["a"] = [0, 1]
	o["d"] = {"b": 2, "c": 3}
	o["e"] = 5
	o["z"] = 6
	return o


def test_context(context):
	"""Basic FilterExecutionContext test."""
	assert context["double"](2) == 4
	assert context["e"] == 5
	assert context["d.c"] == 3
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
		('(a.b==1 && b.c=="2") || (c.d==3)', {"a.b": 1, "b.c": 2, "c.d": 0}, False),
))
def test_string_execution(string, context, res):
	"""Test filter string execution."""
	context = FilterExecutionContext(context)
	assert Filter.from_string(string).execute(context) == res

