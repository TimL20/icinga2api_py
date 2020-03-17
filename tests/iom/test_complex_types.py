# -*- coding: utf-8 -*-
"""
Tests for the iom.simple_types module.
"""

import pytest

from icinga2api_py.iom.base import AbstractIcingaObject, Number, ParentObjectDescription
from icinga2api_py.iom.complex_types import IcingaObjects, IcingaObject, IcingaConfigObject
from icinga2api_py.iom.complex_types import IcingaConfigObjects as RealIcingaConfigObjects
from icinga2api_py.models import APIRequest


# TODO basic init tests with the different objects (test whether they behave like there parents)


@pytest.fixture(scope="module")
def results():
	"""Fixture providing example results."""
	return [{"a": 1, "b": 2}, {"b": 1}]


@pytest.fixture(scope="module")
def icingaobjects(results):
	"""Fixture providing an IcingaObjects object."""
	return IcingaObjects(results, parent_descr=ParentObjectDescription("session"))


@pytest.mark.parametrize("index, raises, type_", (
		(0, False, IcingaObject),
		(-1, False, IcingaObject),
		(slice(0, -1), False, IcingaObjects),
		(4, True, IndexError),
))
def test_icingaobjects_result(icingaobjects, index, raises, type_):
	"""Test IcingaObjects.result()."""
	if raises:
		with pytest.raises(type_):
			_ = icingaobjects.result(index)
	else:
		obj = icingaobjects.result(index)
		assert isinstance(obj, type_)


def test_icingaobjects_convert(results):
	"""Test IcingaObjects.convert()."""
	pod = ParentObjectDescription("session")

	class IcingaObjectsChild(IcingaObjects):
		pass

	res = IcingaObjectsChild.convert(results, pod)
	assert isinstance(res, IcingaObjectsChild)
	assert list(res.results) == results
	assert res.parent_descr == pod

	# Test fail
	with pytest.raises(TypeError):
		_ = IcingaObjectsChild.convert(3, None)


@pytest.fixture
def request_mock(results):
	"""An APIRequest returning the results on send."""
	# TODO better mock...
	req = APIRequest(None, json={
		"joins": ["jointype"]
	})

	class Response:
		def results(self):
			return results

	def send(*args, **kwargs):
		return Response()

	req.send = send
	return req


class IcingaConfigObjects(RealIcingaConfigObjects):
	DESC = {
		"name": "Objecttype",
	}


@pytest.fixture
def icingaconfigobjects(request_mock):
	"""Fixture for an IcingaConfigObject."""
	return IcingaConfigObjects(request=request_mock)


@pytest.mark.parametrize("input, output", (
		("name", ["name"]),
		("state", ["attrs", "state"]),
		(["state"], ["attrs", "state"]),
		("last_check_result.output", ["attrs", "last_check_result", "output"]),
		("objecttype.name", ["attrs", "name"]),
		("jointype.name", ["joins", "jointype", "name"])

))
def test_icingaconfigobject_parse_attrs(icingaconfigobjects, input, output):
	"""Test IcingaConfigObject.parse_attrs()."""
	res = icingaconfigobjects.parse_attrs(input)
	assert res == output


# Modify is tested with iom_e2e
