# -*- coding: utf-8 -*-
"""
Tests for the simple_oo.types module.
"""

from datetime import datetime
import pytest

from ..icinga_mock import mock_session

from icinga2api_py.iom.base import AbstractIcingaObject, Number
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
	yield from mock_session(Session(URL, **API_CLIENT_KWARGS))


@pytest.fixture(scope="function")
def types(session):
	"""The Types object to test."""
	# TODO it would be better to import the things to test; this is not possible right now
	yield session.types


@pytest.mark.parametrize("cls_name, value", (
		("Number", 1),
		("String", "abc"),
		("Boolean", True),
		("Timestamp", 1),
		("Timestamp", datetime.now()),
		("Array", (1, 2, 3)),
		("Dictionary", {1: 2, 2: 3}),
))
def test_basics(types, cls_name, value):
	"""Test the basics for every simple_types type."""
	cls = types.type(cls_name, number=Number.SINGULAR)
	# TODO None as ParentObjectDescription should be discouraged...
	obj = cls(value, None)
	assert obj.value == value
	assert obj == value
	assert cls.convert(value, None) == obj


# TODO add Timestamp tests


def test_array():
	"""Test simple_types.Array."""
	array = Array((0, 1, 2), None)
	assert array.value == [0, 1, 2]
	assert array == [0, 1, 2]
	assert len(array) == 3
	assert array[0] == 0
	# TODO test modification...
	assert Array.convert((0, 1, 2), None) == array


def test_dictionary():
	"""Test simple_types.Dictionary."""
	value = {1: 2, 2: 3}
	dictionary = Dictionary(value, None)
	assert dictionary.value == value
	assert dictionary == value
	assert len(dictionary) == len(value)
	assert list(iter(dictionary)) == list(iter(value))
	assert tuple(dictionary.keys()) == tuple(value)
	assert tuple(dictionary.values()) == tuple(value)
	assert tuple(dictionary.items()) == tuple(value)

	# TODO test modification

	assert Dictionary.convert(value, None) == dictionary
