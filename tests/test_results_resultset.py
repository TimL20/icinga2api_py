# -*- coding: utf-8 -*-
"""
Tests for the important ResultSet class in the results module.
"""

from collections.abc import Sequence
import pytest

from icinga2api_py.results import *


EXAMPLE_RESULTSETS = (
	ResultSet((
		{"a": "b", "b": True, "c": 3, "d": {"a": 1, "b": False}, "e": None, "f": 1.2},
	)),
	# There are hard-coded assumptions about this ResultSet!
	ResultSet((
		{"a": "b", "b": True, "c": 3, "d": {"a": 1, "b": False}, "e": None, "f": 1.2},
		{"a": "b", "b": True, "c": 3, "d": {"a": 1, "b": False}, "e": None, "f": 1.2},
		{"a": "b", "b": True, "c": 3, "d": {"a": 1, "b": False}, "e": None, "f": 1.2},
		{"a": "b", "b": True, "c": 3, "d": {"a": 1, "b": False}, "e": None, "f": 1.2},
	)),
	# To test access methods
	ResultSet((
		{"a": 1, "b": True},
		{"a": 2, "b": True},
		{"a": 3, "b": True},
		{"a": 3, "b": True},
		{"a": 2, "b": True},
		{"a": 3, "b": True},
	))
)


def test_empty():
	"""Tests with empty ResultSet."""
	empty = ResultSet(None)
	# Not loaded yet
	assert not empty.loaded
	# The results have to be a sequence
	assert isinstance(empty.results, Sequence)
	# Because of the results access it's loaded now
	assert empty.loaded
	# An empty sequence has length 0
	assert len(empty) == 0
	# Slicing doesn't change the length
	assert len(empty[:1]) == 0
	# Getting an item from an empty sequence should raise an IndexError
	with pytest.raises(IndexError):
		_ = empty[0]
	# Empty should be a boolean false
	assert not empty
	# String should contain 0
	assert (" 0 " in str(empty) or " no " in str(empty))


@pytest.mark.parametrize("rs", EXAMPLE_RESULTSETS)
def test_notempty(rs):
	"""Tests with a not-empty ResultSet."""
	# Things to be true for every ResultSet object that is not empty
	assert rs.loaded
	assert rs
	assert len(rs) > 0
	# This is not allowed to raise an exception
	assert rs[0] is not None
	# String representations should contain the len
	assert f" {len(rs)} " in str(rs)

	# Test slicing a bit
	assert len(rs) == len(rs[:])
	sliced = rs[-2:]
	assert isinstance(sliced, ResultSet)
	assert 0 < len(sliced) <= 2


def test_eq():
	"""Test __eq__() for ResultSet."""
	assert ResultSet(None) == ResultSet(tuple())
	assert EXAMPLE_RESULTSETS[1] == EXAMPLE_RESULTSETS[1][:]


@pytest.mark.parametrize("attr,expected", (
		("a", ["a"]),
		("a.b.c", ["a", "b", "c"]),
		(["a", "b", "c"], ["a", "b", "c"]),
))
def test_parse_attrs(attr, expected):
	"""Test parse_attrs()."""
	assert ResultSet.parse_attrs(attr) == expected


def test_fields():
	"""Test ResultSet.fields generator."""
	rs = EXAMPLE_RESULTSETS[1]
	# c == 3
	assert set(rs.fields("c")) == {3}
	# Test nokey_value
	assert list(rs.fields("arbitrary", nokey_value=1234)) == [1234 for _ in range(len(rs))]
	# Test raise_nokey
	with pytest.raises(KeyError):
		tuple(rs.fields("arbitrary", raise_nokey=True))


def test_where():
	"""Test ResultSet.where()."""
	rs = EXAMPLE_RESULTSETS[2]
	where22 = rs.where("a", 2)
	assert isinstance(where22, ResultSet)
	assert list(where22.fields("a")) == [2, 2]

	# Test that cls gets called and its results returned
	arg = False

	def fake(lst):
		nonlocal arg
		arg = lst
		return 123
	wherefake = rs.where("z", 0, cls=fake)
	assert wherefake == 123
	assert arg == []


def test_number():
	"""Test ResultSet.number()."""
	rs = EXAMPLE_RESULTSETS[2]
	assert rs.number("a", 3) == 3
	assert rs.number("z", 0) == 0
	assert rs.number("z", KeyError) == len(rs)


def test_all():
	"""Test ResultSet.all()."""
	rs = EXAMPLE_RESULTSETS[2]
	assert rs.all("b", True)
	assert rs.all("z", KeyError)
	assert not rs.all("a", KeyError)
	assert not rs.all("a", 3)


def test_any():
	"""Test ResultSet.any()."""
	rs = EXAMPLE_RESULTSETS[2]
	assert rs.any("a", 1)
	assert rs.any("a", 3)
	assert not rs.any("a", KeyError)
	assert rs.any("z", KeyError)


def test_minmax():
	"""Test ResultSet.min_max()."""
	rs = EXAMPLE_RESULTSETS[2]
	assert rs.min_max("a", 2, 0, 4)
	assert rs.min_max("a", 2, 2, 2)
	assert not rs.min_max("a", 2, 3, 4)
	assert not rs.min_max("a", 2, 0, 1)
	assert rs.min_max("z", 0, 0, 1)
	assert not rs.min_max("z", KeyError, 0, 1)
	assert rs.min_max("z", KeyError, 0, len(rs))
