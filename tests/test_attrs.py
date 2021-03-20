# -*- coding: utf-8 -*-
"""
Tests for the attrs module.
"""

import pytest

from icinga2api_py.attrs import Attribute, AttributeSet


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
	{  # 4 - similar to 3, but with attrs, so that a is the attribute and therefore not eliminated in "taot"
		"init_args": ("attrs.a", ),
		"awareness": False,
		"string": "attrs.a",
		"icinga": "a",
		"joined": "joins.jointype.a",
		"taot": "attrs.a",
	},
	{  # 5
		"init_args": ("otype.x", True),
		"awareness": True,
		"string": "attrs.x",
		"icinga": "otype.x",
		"joined": "joins.jointype.x",
		"object_joined": "joins.otype.x",
	},
	{  # 6
		"init_args": ("otype.x", "otype"),
		"awareness": True,
		"string": "attrs.x",
		"icinga": "otype.x",
		"joined": "joins.jointype.x",
		"object_joined": "joins.otype.x",
	},
	{  # 7
		"init_args": ("joins.jtype.x", ),
		"awareness": False,
		"string": "joins.jtype.x",
		"icinga": "jtype.x",
		"joined": "joins.jointype.x",
	},
	{  # 8
		"init_args": ("joins.jtype.x", True),
		"awareness": False,  # Awareness should be ignored, because "joins" is not a valid object type
		"string": "joins.jtype.x",
		"icinga": "jtype.x",
		"joined": "joins.jointype.x",
	},
	{  # 9
		"init_args": ("joins.jtype.x", "otype"),
		"awareness": True,
		"string": "joins.jtype.x",
		"icinga": "jtype.x",
		"joined": "joins.jointype.x",
		"object_joined_overriden": "joins.otype.x",

	},
	{  # 10
		"init_args": ("x", ),
		"awareness": False,
		"string": "x",
		"icinga": "x",
		"joined": "joins.jointype.x",
	},
	{  # 11
		"init_args": ("otype", True),
		"awareness": True,
		"string": "attrs",
		"icinga": "otype",
		"joined": "joins.jointype",
		"object_joined": "joins.otype",
	},
	{  # 12
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
	{
		"object_type": None,  # No type awareness
		"attrs": (
			"attrs.a", "attrs.b", "joins.jo",
		),
		"res": {"attrs.a", "attrs.b", "joins.jo"},
		"type_b": {"attrs.a", "attrs.b", "joins.jo"},  # attrs because type is set to b and
		"contains": (
			"attrs.a.b",  # Because of attrs.a
		),
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
