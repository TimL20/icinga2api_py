# -*- coding: utf-8 -*-
"""
Test for the attrs module.
"""

import pytest

from icinga2api_py.attrs import Attribute


TEST_DATA = (
	{  # 0
		"init_args": ("attrs.x", ),
		"awareness": False,
		"string": "attrs.x",
		"joined": "joins.jointype.x",
	},
	{  # 1
		"init_args": ("attrs.x", True),
		"awareness": False,  # Awareness should be ignored, because "attrs" is not a valid type
		"string": "attrs.x",
		"joined": "joins.jointype.x",
	},
	{  # 2
		"init_args": ("attrs.x", False, "otype"),
		"awareness": True,
		"string": "attrs.x",
		"joined": "joins.jointype.x",
	},
	{  # 3
		"init_args": ("a.x", ),
		"awareness": False,
		"string": "a.x",
		"joined": "joins.jointype.a.x",
		"taot": "x",
	},
	{  # 4
		"init_args": ("otype.x", True),
		"awareness": True,
		"string": "attrs.x",
		"joined": "joins.jointype.x",
	},
	{  # 5
		"init_args": ("otype.x", False, "otype"),
		"awareness": True,
		"string": "attrs.x",
		"joined": "joins.jointype.x",
	},
	{  # 6
		"init_args": ("joins.jtype.x", ),
		"awareness": False,
		"string": "joins.jtype.x",
		"joined": "joins.jointype.x",
	},
	{  # 7
		"init_args": ("joins.jtype.x", True),
		"awareness": False,  # Awareness should be ignored, because "joins" is not a valid object type
		"string": "joins.jtype.x",
		"joined": "joins.jointype.x",
	},
	{  # 8
		"init_args": ("joins.jtype.x", False, "otype"),
		"awareness": True,
		"string": "joins.jtype.x",
		"joined": "joins.jointype.x",
	},
	{  # 9
		"init_args": ("x", ),
		"awareness": False,
		"string": "x",
		"joined": "joins.jointype.x",
	},
	{  # 10
		"init_args": ("otype", True),
		"awareness": True,
		"string": "attrs",
		"joined": "joins.jointype",
	},
	{  # 11
		"init_args": ("otype", False, "otype"),
		"awareness": True,
		"string": "attrs",
		"joined": "joins.jointype",
	},
	# Unusual testdata (inputs not as expected), to test how the functionality deals with it...
	# TODO add Edge case: both aware and object_type are set; one must have precedence
)
IDS = [f"{i}:{d['string']}" for i, d in enumerate(TEST_DATA)]


@pytest.fixture(scope="function", params=[data_set for data_set in TEST_DATA], ids=IDS)
def tdata_set(request):
	data_set = request.param
	data_set["obj"] = Attribute(*data_set["init_args"])
	return data_set


def test_attribute_basics(tdata_set):
	"""Test Attribute.{object_aware,__str__}."""
	obj = tdata_set["obj"]
	assert obj.object_type_aware == tdata_set["awareness"]
	assert str(obj) == tdata_set["string"]


def test_attribute_jointype(tdata_set):
	"""Test Attribute.join_type property."""
	obj = tdata_set["obj"]
	obj.join_type = "jointype"
	assert obj.join_type == "jointype"
	assert str(obj) == tdata_set["joined"]


def test_attribute_objecttype(tdata_set):
	"""Test Attribute.object_type property."""
	obj = tdata_set["obj"]
	obj.object_type = "a"
	assert obj.object_type == "a"
	assert str(obj) == tdata_set.get("taot", tdata_set["string"])
