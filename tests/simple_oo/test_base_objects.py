# -*- coding: utf-8 -*-
"""
Tests for the simple_oo.base_objects module.
"""

import pytest
from requests import Response

from icinga2api_py import API
from icinga2api_py.models import APIRequest
from icinga2api_py.simple_oo.base_objects import Icinga2Object, Icinga2Objects, ActionMixin


# These three belong together
EXAMPLE_NAMES = (
	tuple(),
	("localhost", ),
	("localhost", "icinga"),
	("localhost", "icinga", "testhost"),
)
EXAMPLE_FILTERS = (
	None,  # This is debatable...
	'host.name=="localhost"',
	'host.name=="localhost" || host.name=="icinga"',
	'host.name=="localhost" || host.name=="icinga" || host.name=="testhost"',
)
EXAMPLE_OBJECTS = (
	Icinga2Objects(tuple()),
	Icinga2Objects((
		{"type": "Host", "name": "localhost", "attrs": {"state": 0}},
	)),
	Icinga2Objects((
		{"type": "Host", "name": "localhost", "attrs": {"state": 0}},
		{"type": "Host", "name": "icinga", "attrs": {"state": 0}},
	)),
	Icinga2Objects((
		{"type": "Host", "name": "localhost", "attrs": {"state": 0}},
		{"type": "Host", "name": "icinga", "attrs": {"state": 0}},
		{"type": "Host", "name": "testhost", "attrs": {"state": 0}},
	)),
)


@pytest.mark.parametrize("i", [i for i in range(len(EXAMPLE_OBJECTS))])
def test_eq(i):
	"""Test equality check."""
	assert EXAMPLE_OBJECTS[i] == Icinga2Objects(EXAMPLE_OBJECTS[i].results)


def test_type():
	"""Test type property."""
	assert Icinga2Objects(({"type": "test"},)).type == "test"
	assert Icinga2Objects(tuple()).type is None


@pytest.mark.parametrize("i", [i for i in range(len(EXAMPLE_OBJECTS))])
def test_objects_filter(i):
	"""Test Icinga2Objects.object_filter()."""
	obj = EXAMPLE_OBJECTS[i]
	res = EXAMPLE_FILTERS[i]
	assert obj.objects_filter() == res


@pytest.mark.parametrize("i", [i for i in range(3)])
def test_result(i):
	"""Test Icinga2Objects.result() (and therefore also a bit result_as())."""
	res = EXAMPLE_OBJECTS[3][i]
	assert isinstance(res, Icinga2Object)
	assert res["name"] == EXAMPLE_NAMES[3][i]


#######################################################################################################################
# Test that need a request (and at first the deeply faked request)
#######################################################################################################################


@pytest.fixture
def deep_fake_request():
	"""Fake a APIRequest."""

	class FakeApiClient(API):
		def __init__(self):
			super().__init__("notempty")
			self.base_url = ""  # Overwrite with empty base

		@property
		def request_class(self):
			def fake_class(_, method, url, json):
				"""Fake a calls that has a call method using two functions."""
				def inner_call():
					return method, url, json
				return inner_call

			return fake_class

	class FakeResponseObject(Response):
		def results(self, **json_kwargs):
			return EXAMPLE_OBJECTS[3].results

	class FakeApiRequestObject:
		@property
		def api(self):
			return FakeApiClient()

		def __call__(self, *args, **kwargs):
			return FakeResponseObject()

		send = __call__

		def clone(self):
			return self

	return FakeApiRequestObject()


@pytest.fixture
def fake_request2():
	"""Small APIRequest patch that avoids getting a response."""

	class FakeRequest2(APIRequest):
		def send(self, params=None):
			return self

	class FakeApiClient2(API):
		def __init__(self):
			super().__init__("notempty")
			self.base_url = ""  # Overwrite with empty base

		@property
		def request_class(self):
			return FakeRequest2

	return FakeRequest2(FakeApiClient2(), json={})


class ActionMixinTestClass(Icinga2Objects, ActionMixin):
	"""Class to test the ActionMixin with."""


def test_action(deep_fake_request):
	"""Test Icinga2Objects.action()."""
	obj = ActionMixinTestClass(request=deep_fake_request)
	# Fake returns a tuple of: method, url, json
	method, url, body = obj.action("test-action", t1="param1", p2="param2")
	assert method == "POST"
	assert url == "actions/test-action"
	assert body == {
		"type": "Host", "filter": EXAMPLE_FILTERS[3],
		"t1": "param1", "p2": "param2",
	}


def test_modify(fake_request2):
	"""Test Icinga2Objects.modify()."""
	obj = Icinga2Objects(request=fake_request2)
	attrs = {"a": "b", "c": 1}
	ret = obj.modify(attrs)
	assert ret.method_override == "POST"
	assert ret.json["attrs"] == attrs


def test_delete(fake_request2):
	"""Test Icinga2Objects.delete()."""
	obj = Icinga2Objects(request=fake_request2)
	ret = obj.delete()
	assert ret.method_override == "DELETE"
