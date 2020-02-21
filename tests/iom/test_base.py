# -*- coding: utf-8 -*-
"""
Tests for the simple_oo.base module.
"""

import pytest

from icinga2api_py.iom.base import ParentObjectDescription, AbstractIcingaObject


class FakeParent:
	INDICATOR = -1

	@property
	def parent_descr(self):
		return ParentObjectDescription(session=self.INDICATOR)


fake_parent = FakeParent()


@pytest.mark.parametrize("session, parent, field, raises, r_session", (
		(0, fake_parent, 1,			False, fake_parent.INDICATOR),
		(None, fake_parent, 1,		False, fake_parent.INDICATOR),
		(0, None, 1,				True, 0),
		(0, fake_parent, None,		True, 0),
		(None, None, 1,				True, 0),
		(0, None, None,				False, 0),
		(None, fake_parent, None,	True, 0),
		(None, None, None,			True, 0),
), ids=[str(i) for i in range(8)])
def test_parentobjectdescription(session, parent, field, raises, r_session):
	"""Test ParentObjectDescription functionality."""
	if raises:
		with pytest.raises(ValueError):
			ParentObjectDescription(session, parent, field)
	else:
		pod = ParentObjectDescription(session, parent, field)
		assert pod.parent == parent
		assert pod.field == field
		assert pod.session == r_session

		# Test equality check
		assert pod == ParentObjectDescription(session, parent, field)


DESC = {"abstract": False, "name": "TYPENAME", "plural_name": "TYPENAMES", "prototype_keys": []}
FIELDS = {
	"field_a": {
		"array_range": 0,
		"attributes": {
			"config": True,
			"deprecated": False,
			"navigation": False,
			"no_user_modify": False,
			"no_user_view": False,
			"required": False,
			"state": False,
		},
		"id": 70,
		"type": "Number",
	}
}


@pytest.fixture(scope="function")
def absicingao():
	"""AbstractIcingaObject fixture."""
	obj = AbstractIcingaObject(parent_descr=ParentObjectDescription(session="Fruitsession"))
	obj.DESC = DESC
	obj.FIELDS = FIELDS
	return obj


def test_type(absicingao):
	"""Test AbstractIcingaObject.type."""
	assert absicingao.type == "TYPENAME"


def test_permissions(absicingao):
	"""Test AbstractIcingaObject.type."""
	assert absicingao.permissions("field_a") == (False, False)
	# Manipulate
	absicingao.FIELDS["field_a"]["attributes"]["no_user_view"] = "nuv"
	absicingao.FIELDS["field_a"]["attributes"]["no_user_modify"] = "num"
	assert absicingao.permissions("field_a") == ("nuv", "num")

	# Test defaults
	del absicingao.FIELDS["field_a"]["attributes"]["no_user_view"]
	del absicingao.FIELDS["field_a"]["attributes"]["no_user_modify"]
	assert absicingao.permissions("field_a") == (True, True)
	assert absicingao.permissions("notexistant") == (True, True)


def test_parent_descr(absicingao):
	"""Test AbstractIcingaObject.parent_descr and AbstractIcingaObject.session."""
	assert absicingao.parent_descr.session == "Fruitsession"
	assert absicingao.session == "Fruitsession"


def test_abstract_convert():
	"""Test AbstractIcingaObject.convert."""
	with pytest.raises(TypeError) as excinfo:
		AbstractIcingaObject.convert(None, None)
	assert "conversion" in str(excinfo.value).lower()
