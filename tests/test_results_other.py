# -*- coding: utf-8 -*-
"""
Test the classes of the results module other than ResultSet (that is tested in test_results_resultset).
"""

import pytest
from requests import Response

from icinga2api_py.results import *


@pytest.fixture
def api_response():
	"""Returns a fake APIResponse object."""

	class FakeResponseObject(Response):
		def results(self, **json_kwargs):
			return json_kwargs,

	return FakeResponseObject()


@pytest.fixture
def api_request(api_response):
	"""Returns a fake APIRequest object."""

	class FakeApiRequestObject:
		def __call__(self, *args, **kwargs):
			return api_response

		send = __call__

	return FakeApiRequestObject()


@pytest.fixture
def advanced_api_request(api_response):
	"""Returns a callable that returns a fake APIRequest object."""

	class FakeApiRequestObject:
		def __init__(self, stats):
			self.stats = stats

		def __call__(self, *args, **kwargs):
			self.stats["calls"] += 1
			return api_response

		send = __call__

	return FakeApiRequestObject


ALL_CLASSES = (
	ResultsFromResponse,
	ResultsFromRequest,
	CachedResultSet,
	Result,
)
RESPONSE_CLASSES = ALL_CLASSES[:3]
REQUEST_CLASSES = ALL_CLASSES[1:3]


@pytest.mark.parametrize("cls", ALL_CLASSES, ids=[cls.__name__ for cls in ALL_CLASSES])
def test_results_init(cls):
	"""Test results-only init."""
	results = ({"a": 1},)
	rs = cls(results)
	assert rs.results == results


@pytest.mark.parametrize("cls", RESPONSE_CLASSES, ids=[cls.__name__ for cls in RESPONSE_CLASSES])
@pytest.mark.parametrize("json_kwargs", ({}, {"a": 1}))
def test_response_init(cls, json_kwargs, api_response):
	"""Test init with a response."""
	rs = cls(response=api_response, json_kwargs=json_kwargs)
	# Not loaded at first
	assert rs.loaded is False
	assert rs.response == api_response
	assert rs.results == api_response.results(**json_kwargs)
	# Loaded now because results were accessed
	assert rs.loaded is True


@pytest.mark.parametrize("cls", REQUEST_CLASSES, ids=[cls.__name__ for cls in REQUEST_CLASSES])
@pytest.mark.parametrize("json_kwargs", ({}, {"a": 1}))
def test_request_init(cls, json_kwargs, api_request):
	"""Test init with a request."""
	rs = cls(request=api_request, json_kwargs=json_kwargs)
	# Not loaded at first
	assert rs.loaded is False
	assert rs.request == api_request
	resp = api_request()
	assert rs.response == resp
	assert rs.results == resp.results(**json_kwargs)


def test_resultsfromrequest_eq():
	"""Test ResultsFromRequest.__eq__()."""
	rs1 = ResultsFromRequest(1)
	rs2 = ResultsFromRequest(1)
	# If the requests are equal, nothing else should ever be checked
	assert rs1 == rs2


def test_caching(advanced_api_request, monkeypatch):
	"""Test caching in CachedResultSet."""
	stats = dict()
	api_request = advanced_api_request(stats)

	# Cache time infinity
	rs = CachedResultSet(request=api_request, cache_time=float("inf"))
	stats["calls"] = 0
	_ = rs.results
	assert stats["calls"] == 1
	_ = rs.results
	assert stats["calls"] == 1
	rs.invalidate()
	_ = rs.results
	assert stats["calls"] == 2

	stats["calls"] = 0
	rs = CachedResultSet(request=api_request, cache_time=-1)
	_ = rs.results
	assert stats["calls"] == 1
	_ = rs.results
	assert stats["calls"] == 2

	# Test hold
	assert not rs.held
	with rs:
		_ = rs.results
		assert stats["calls"] == 2
		assert rs.held
	assert not rs.held
	_ = rs.results
	assert stats["calls"] == 3


def test_resultlist():
	"""Test ResultList."""
	lst = ResultList(({"a": 1}))
	assert lst

	# Test item get/set/del
	lst.insert(0, {"a": 0})
	assert lst[0]["a"] == 0
	lst[0] = {"b": 1}
	assert lst[0]["b"] == 1
	del lst[0]
	res = lst[0]
	with pytest.raises(KeyError):
		_ = res["b"]

	# Test slicing
	assert len(lst) == len(lst[:])
	sliced = lst[-2:]
	assert isinstance(sliced, ResultList)
	assert 0 < len(sliced) <= 2

	# Attribute access
	assert lst.all("d.a", 1)


def test_result():
	"""Test the Result class."""
	d = {"a": "b", "d": {"a": 1, "b": False}}
	res = Result(d)
	assert res == Result((d, ))
	# Test item access
	assert res["a"] == "b"
	assert "a" in res
	assert list(res.keys()) == ["a", "d"]
	assert tuple(res.items()) == tuple(d.items())
	assert tuple(res.values()) == ("b", d["d"])

	assert len(res) == 1
	assert next(iter(res)) == res

	# Should not raise IndexError
	_ = res[0]
	with pytest.raises(IndexError):
		_ = res[1]
