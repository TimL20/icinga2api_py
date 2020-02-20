# -*- coding: utf-8 -*-
"""
Tests for the iom.types module.
"""

from collections.abc import Mapping
from operator import itemgetter
import pytest

from ..icinga_mock import mock_session

from icinga2api_py.iom.base import AbstractIcingaObject, Number
from icinga2api_py.iom.complex_types import IcingaObject, IcingaObjects, IcingaConfigObject
from icinga2api_py.iom.simple_types import Array, Dictionary
import icinga2api_py.iom.types as types_module
from icinga2api_py.iom.session import Session


URL = "http://icinga:1234/v1/"
API_CLIENT_KWARGS = {
	"verify": False,
	"auth": ("user", "pass"),
	"attr1": "value1"
}


@pytest.fixture(scope="module")
def session() -> Session:
	"""Icinga Session (client)."""
	session = Session(URL, **API_CLIENT_KWARGS)
	mock_session(session)
	# Types object is already created at this point and therefore would remain "unmocked"
	mock_session(session.types.request.api)
	with session:
		yield session


@pytest.fixture(scope="function")
def types(session):
	"""The Types object to test."""
	yield session.types


def test_basic(types):
	"""Test basic things."""
	assert types.cache_time == float("inf")
	assert types.request == types.iclient.api().types.get


TYPES_RESULT_TEST_PARAMETERS = (
	("Object", tuple, True),
	("boolean", tuple, True),
	("DICTIONARY", tuple, True),
	("array", tuple, True),
	("Host", tuple, True),
	("Hosts", tuple, False),
	("notexistingtype", KeyError, None),
)


@pytest.mark.parametrize(
	"item,exp_type,ret_1", TYPES_RESULT_TEST_PARAMETERS,
	ids=list(map(itemgetter(0), TYPES_RESULT_TEST_PARAMETERS))
)
def test_result(types, item, exp_type, ret_1):
	"""Test Types.result()."""
	if issubclass(exp_type, BaseException):
		with pytest.raises(exp_type):
			_ = types.result(item)
	else:
		ret = types.result(item)
		assert isinstance(ret, exp_type)
		assert ret[1] == ret_1


@pytest.mark.parametrize("item, exp_type", (
		("Object", IcingaObject),
		("ConfigObject", IcingaConfigObject),
		("Array", Array),
		("Dictionary", Dictionary),
		("Host", None),
		("Services", None),
		("CheckResult", None),
		# TODO it would be better to test Number, String and Boolean explicitely (but import isn't possible right now)
))
def test_type_general(types, item, exp_type):
	"""Test Types.type() in general (number parameter is tested elsewhere)."""
	cls = types.type(item, number=Number.SINGULAR)
	# Check namespace
	assert hasattr(cls, "__module__")
	assert isinstance(cls.DESC, Mapping)
	assert isinstance(cls.FIELDS, Mapping)

	if exp_type is not None:
		# Check whether the return value is exp_type
		assert cls is exp_type

	assert issubclass(cls, AbstractIcingaObject)


@pytest.mark.parametrize("item, number, expected_type", (
		("object", "singular", IcingaObject),
		("objects", "singular", IcingaObject),
		("object", "plural", IcingaObjects),
		("objects", "plural", IcingaObjects),
		("object", "irrelevant", IcingaObject),
		("objects", "irrelevant", IcingaObjects),
))
def test_type_number(types, item, number, expected_type):
	"""Test Types.type() number parameter."""
	number = getattr(Number, number.upper())
	cls = types.type(item, number=number)
	assert cls is expected_type
