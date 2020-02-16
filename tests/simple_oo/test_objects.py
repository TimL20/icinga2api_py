# -*- coding: utf-8 -*-
"""
Tests for the simple_oo.objects module.

All of the classes extend Icinga2Object[s], only the additional things are tested.
"""

import pytest

from icinga2api_py import API
from icinga2api_py.models import APIRequest
from icinga2api_py.simple_oo.objects import *


@pytest.fixture
def fake_request():
	"""A faked APIRequest."""

	class FakeApiRequest(APIRequest):
		def send(self, params=None):
			return self

	class FakeApiClient(API):
		def __init__(self):
			super().__init__("notempty")
			self.base_url = ""  # Overwrite with empty base

		@property
		def request_class(self):
			return FakeApiRequest

	return FakeApiRequest(FakeApiClient(), json={})


@pytest.fixture
def objects_init_params(fake_request):
	"""Init parameters for Icinga2Objects."""
	return {
		"results": ({"name": "objectname", "type": "Objecttype", "attrs": {"state": 1, "host_name": "Hostname"}}, ),
		"request": fake_request
	}


def test_host_services(objects_init_params):
	"""Test Host.services property."""
	host = Host(**objects_init_params)
	res = host.services
	assert res.method_override == "GET"
	assert res.url == "objects/services"
	assert res.json == {"filter": 'host.name=="objectname"'}


@pytest.mark.parametrize("cls", (
	Hosts, Host, Services, Service
))
def test_action_existance(cls):
	"""Test for all required classes that they have an action() method, functionality is tested with base_objects."""
	assert hasattr(cls, "action")


@pytest.mark.parametrize("cls,s_class", (
		(Hosts, Host),
		(Services, Service),
		(Templates, Template),
))
def test_special_results(cls, s_class, objects_init_params):
	"""Test the special .result() methods of some classes."""
	objects = cls(**objects_init_params)
	obj = objects.result(0)
	assert isinstance(obj, s_class)


def test_service_host(objects_init_params):
	"""Test Service.host property."""
	service = Service(**objects_init_params)
	host = service.host
	assert host.method_override == "GET"
	assert host.url == "objects/hosts/Hostname"


def test_template_nomodify():
	"""Test, that modify and delete are not allowed for Template."""
	templ = Templates()
	with pytest.raises(TypeError):
		templ.modify({})
	with pytest.raises(TypeError):
		templ.delete()
