# -*- coding: utf-8 -*-
"""
Tests for the iom.simple_types module.
"""

import datetime
import pytest

from ..icinga_mock import mock_session_handler

from icinga2api_py.iom.base import AbstractIcingaObject, Number, ParentObjectDescription
from icinga2api_py.iom.simple_types import Timestamp, Array, Dictionary
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
	yield from mock_session_handler(Session(URL, **API_CLIENT_KWARGS))


@pytest.fixture(scope="function")
def types(session):
	"""The Types object to test."""
	# TODO it would be better to import the things to test; this is not possible right now
	yield session.types


DEFAULT_POD = ParentObjectDescription(0)


@pytest.mark.parametrize("cls_name, value", (
		("Number", 1),
		("String", "abc"),
		("Boolean", True),
		("Timestamp", 1),  # Timestamp doesn't work with datetime as init arg
		("Array", [1, 2, 3]),
		("Dictionary", {"a": 1, "b": 2}),
))
def test_basics(types, cls_name, value):
	"""Test the basics for every simple_types type."""
	cls = types.type(cls_name, number=Number.SINGULAR)
	obj = cls(value, DEFAULT_POD)
	assert obj.value == value
	assert obj == value
	assert cls.convert(value, DEFAULT_POD) == obj


DATETIME = datetime.datetime.strptime("2020-01-02 04:06 +0000", "%Y-%m-%d %H:%M %z")


@pytest.mark.parametrize("value", (
		int(DATETIME.timestamp()),
		float(DATETIME.timestamp()),
		DATETIME,
))
def test_timestamp_compat(value):
	"""Test that Timestamp is compatible to both float/int and datetime objects."""
	ts = Timestamp.convert(value, DEFAULT_POD)
	if isinstance(value, (float, int)):
		assert ts.value == value
	else:
		assert ts.datetime == value

	assert ts.hour == 4
	assert ts.year == 2020

	assert ts.strftime("%Y-%m-%d %H:%M %z") == "2020-01-02 04:06 +0000"


def test_array():
	"""Test simple_types.Array."""
	array = Array((0, 1, 2), DEFAULT_POD)
	assert array.value == [0, 1, 2]
	assert array == [0, 1, 2]
	assert len(array) == 3
	assert array[0] == 0
	# TODO test modification...


def test_dictionary():
	"""Test simple_types.Dictionary."""
	value = {"1": 2, "2": 3}
	dictionary = Dictionary(value, DEFAULT_POD)
	assert len(dictionary) == len(value)
	assert list(iter(dictionary)) == list(iter(value))
	assert tuple(dictionary.keys()) == tuple(value.keys())
	assert tuple(dictionary.values()) == tuple(value.values())
	assert tuple(dictionary.items()) == tuple(value.items())


@pytest.mark.parametrize("cls, value, res", (
		(Dictionary, {1: {2: 3}}, {"1": {"2": 3}}),
		(Dictionary, {1: [{2: 3}]}, {"1": [{"2": 3}]}),
		(Array, [0, {1: [{2: 3}]}], [0, {"1": [{"2": 3}]}])
))
def test_nested(cls, value, res):
	"""Test nested Dictionary / Array objects, especially their key conversion to strings."""
	obj = cls(value, DEFAULT_POD)
	assert obj == res
