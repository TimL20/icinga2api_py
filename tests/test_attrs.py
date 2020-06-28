# -*- coding: utf-8 -*-
"""
Test for the attrs module.
"""

import pytest

from icinga2api_py.attrs import Attribute, AttributeSet, Operator, Filter, FilterExecutionContext


# Test data with the following key-value pairs (except the init_args they are all only checked properties):
# init_args: Sequence of arguments the Attribute is initiated with
# awareness: Whether the attribute object should be type-aware
# string: String representation in results format
# icinga: String representation in Icinga format
# joined: What the string representation should look like, if the join_type is set to "jointype"
# object_joined: What the string representation should look like, if the object type is set as the join type
# 					(defaults to string)
# object_joined_overriden: What the string representation should look like, if the object type is set as the join type
# 							with override_jointype=True. (defaults to object_joined)
# taot: What the string representation should look like (if not as before) after the object_type is set to "a"
TEST_DATA = (
	{  # 0
		"init_args": ("attrs.x", ),
		"awareness": False,
		"string": "attrs.x",
		"icinga": "x",
		"joined": "joins.jointype.x",
	},
	{  # 1
		"init_args": ("attrs.x", True),
		"awareness": False,  # Awareness should be ignored, because "attrs" is not a valid type
		"string": "attrs.x",
		"icinga": "x",
		"joined": "joins.jointype.x",
	},
	{  # 2
		"init_args": ("attrs.x", "otype"),
		"awareness": True,
		"string": "attrs.x",
		"icinga": "otype.x",
		"joined": "joins.jointype.x",
		"object_joined": "joins.otype.x",
	},
	{  # 3
		"init_args": ("a.x", ),
		"awareness": False,
		"string": "a.x",
		"icinga": "a.x",
		"joined": "joins.jointype.a.x",
		"taot": "x",
	},
	{  # 4
		"init_args": ("otype.x", True),
		"awareness": True,
		"string": "attrs.x",
		"icinga": "otype.x",
		"joined": "joins.jointype.x",
		"object_joined": "joins.otype.x",
	},
	{  # 5
		"init_args": ("otype.x", "otype"),
		"awareness": True,
		"string": "attrs.x",
		"icinga": "otype.x",
		"joined": "joins.jointype.x",
		"object_joined": "joins.otype.x",
	},
	{  # 6
		"init_args": ("joins.jtype.x", ),
		"awareness": False,
		"string": "joins.jtype.x",
		"icinga": "jtype.x",
		"joined": "joins.jointype.x",
	},
	{  # 7
		"init_args": ("joins.jtype.x", True),
		"awareness": False,  # Awareness should be ignored, because "joins" is not a valid object type
		"string": "joins.jtype.x",
		"icinga": "jtype.x",
		"joined": "joins.jointype.x",
	},
	{  # 8
		"init_args": ("joins.jtype.x", "otype"),
		"awareness": True,
		"string": "joins.jtype.x",
		"icinga": "jtype.x",
		"joined": "joins.jointype.x",
		"object_joined_overriden": "joins.otype.x",

	},
	{  # 9
		"init_args": ("x", ),
		"awareness": False,
		"string": "x",
		"icinga": "x",
		"joined": "joins.jointype.x",
	},
	{  # 10
		"init_args": ("otype", True),
		"awareness": True,
		"string": "attrs",
		"icinga": "otype",
		"joined": "joins.jointype",
		"object_joined": "joins.otype",
	},
	{  # 11
		"init_args": ("otype", "otype"),
		"awareness": True,
		"string": "attrs",
		"icinga": "otype",
		"joined": "joins.jointype",
		"object_joined": "joins.otype",
	},
)
IDS = [f"{i}:{d['string']}" for i, d in enumerate(TEST_DATA)]


@pytest.fixture(scope="function", params=[data_set for data_set in TEST_DATA], ids=IDS)
def tdata_attr(request):
	data_set = request.param
	data_set["obj"] = Attribute(*data_set["init_args"])
	return data_set


def test_attribute_basics(tdata_attr):
	"""Test Attribute.{object_aware,__str__}."""
	obj = tdata_attr["obj"]
	assert obj.object_type_aware == tdata_attr["awareness"]
	assert obj.description(Attribute.Format.RESULTS) == tdata_attr["string"]
	assert obj.description(Attribute.Format.ICINGA) == str(obj) == tdata_attr["icinga"]

	# Test that these don't fail
	assert bool(repr(obj))
	assert bool(hash(obj))


def test_attribute_jointype(tdata_attr):
	"""Test Attribute.amend_join_type()."""
	obj = tdata_attr["obj"].amend_join_type("jointype")
	assert obj.join_type == "jointype"
	assert obj.description(Attribute.Format.RESULTS) == tdata_attr["joined"]


def test_attribute_object_joined(tdata_attr):
	"""Test Attribute.amend_object_type() with as_jointype=True."""
	obj = tdata_attr["obj"]
	object_joined = tdata_attr.get("object_joined", tdata_attr["string"])
	object_joined_overriden = tdata_attr.get("object_joined_overriden", object_joined)
	joined = obj.amend_object_type("objecttype", as_jointype=True)
	assert joined.description(Attribute.Format.RESULTS) == object_joined
	joined = obj.amend_object_type("objecttype", as_jointype=True, override_jointype=True)
	assert joined.description(Attribute.Format.RESULTS) == object_joined_overriden


def test_attribute_objecttype(tdata_attr):
	"""Test Attribute.amend_object_type()."""
	obj = tdata_attr["obj"].amend_object_type("a")
	assert obj.object_type == "a"
	assert obj.description(Attribute.Format.RESULTS) == tdata_attr.get("taot", tdata_attr["string"])


@pytest.mark.parametrize("init_args", [d["init_args"] for d in TEST_DATA], ids=IDS)
def test_attribute_eq(init_args):
	"""Test Attribute.__eq__()."""
	assert Attribute(*init_args) == Attribute(*init_args)


#######################################################################################################################
# Test AttributeSet
#######################################################################################################################

SET_DATA = (
	{
		"object_type": "a",
		"attrs": (
			"a.b", "attrs.b",  # These are the same
			"b.c", "joins.b.c",  # These two are also the same
		),
		"res": {"attrs.b", "joins.b.c"},
		"type_b": {"joins.a.b", "attrs.c"},
		"contains": ("a.b.c", "b.c.d"),
	},
	{
		"object_type": "a",
		"attrs": ("attrs", "joins.b"),
		"res": {"attrs", "joins.b"},
		"type_b": {"joins.a", "attrs"},
		"contains": (
			"a.b.c",  # Because of attrs of object a
			"b.c.d",  # Because of joins.b
			Attribute("attrs", object_type="a"),  # attrs of object a
			Attribute("attrs", object_type="b"),  # attrs of object b = joins.b of object a
		)
	},
)

SET_IDS = [str(i) for i, d in enumerate(SET_DATA)]


@pytest.fixture(scope="function", params=[data_set for data_set in SET_DATA], ids=SET_IDS)
def tdata_set(request):
	data_set = request.param
	data_set["set"] = AttributeSet(data_set["object_type"], data_set["attrs"])
	return data_set


def test_attributeset_objecttype(tdata_set):
	"""Test the object_type handling of AttributeSet."""
	assert set(attr.description(Attribute.Format.RESULTS) for attr in tdata_set["set"]) == tdata_set["res"]

	tdata_set["set"].object_type = "b"
	assert tdata_set["set"].object_type == "b"
	assert set(attr.description(Attribute.Format.RESULTS) for attr in tdata_set["set"]) == tdata_set["type_b"]


def test_attributeset_contain(tdata_set):
	"""Test AttributeSet.__contains__()."""
	obj = tdata_set["set"]

	# Set must contain every attr of the representation
	for attr in tdata_set["res"]:
		# Set must contain every attr of the representation
		assert attr in obj

	for attr in tdata_set["contains"]:
		assert attr in obj


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
	assert Operator("##", Operator.Type.COMPARISON, None).register() is False
	assert o.register(True)

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
