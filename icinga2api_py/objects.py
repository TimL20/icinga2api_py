# -*- coding: utf-8 -*-
"""Object oriented access to Icinga2 and it's objects.
"""

import logging
import sys
import collections.abc
from .api import API
from .base import StreamClient
from .base import NotExactlyOne
from .base import Icinga2Objects
from .base import Icinga2Object


def parse_filter(filter):
	if isinstance(filter, collections.abc.Mapping):
		filterlist = []
		for attribute, value in filter.items():
			filterlist.append("{}=={}".format(attribute, value))
		filter = " && ".join(filterlist)
	return filter


class Icinga2:
	"""Central class of this OOP interface for the Icinga2 API.
	An object of this class is needed for a lot of things of the OOP interface."""
	def __init__(self, client, cache_time=60):
		self.client = client
		self.cache_time = cache_time

	def __getattr__(self, item):
		return self.s(item)

	def s(self, item):
		return self.QueryBuilder(self).s(item)

	class QueryBuilder:
		def __init__(self, icinga):
			self.icinga = icinga
			self.query = icinga.client

		def __getattr__(self, item):
			return self.s(item)

		def s(self, item):
			self.query = self.query.s(item)
			return self

		def __call__(self, *args, **kwargs):
			if isinstance(self.query, API.Request):
				# Guess type from URL
				type = self.query.url[self.query.url.find(self.client.base_url)+len(self.client.base_url):]
				type = "" if not type else (type[:-1] if type[-1:] == "s" else type).split("/", 2)[0]
				if type == "object":
					type = self.query.url[self.query.url.find(self.client.base_url) + len(self.client.base_url) + 7:]
					type = "" if not type else (type[:-1] if type[-1:] == "s" else type).split("/", 3)
					type = type[0] if len(type[0]) else type[1]
				logging.getLogger(__name__).debug("Assumed type %s from URL %s", type, self.query.url)
				name = None if not args else args[0]  # Also possible to set via kwargs
				return self.icinga.object_from_query(type, self.query, name, **kwargs)
			# else: (self.query is not an API.Request)
			self.query = self.query(*args, **kwargs)
			return self

	def object_from_query(self, type, query, name=None, **kwargs):
		"""Get a appropriate python object to represent whatever is queried with the query.
		This method assumes, that a named object is singular (= one object). The name is not used for building the query,
		but it's passed to any Icinga2Object constructor.
		Remaining kwargs are passed to the constructor (Icinga2Object, Host, ...)."""
		class_ = getattr(sys.modules[__name__], type.title(), None)
		initargs = {"cache_time": self.cache_time}
		singular = name is not None  # it's one object if it has a name
		if singular:
			initargs["name"] = name
		initargs.update(kwargs)
		if class_ is not None:
			return class_(query, **initargs)
		if singular:
			return Icinga2Object(query, **initargs)
		return Icinga2Objects(query, **initargs)

	def create_object(self, type, name, templates, attrs, ignore_on_error=False):
		"""Create an Icinga2 object through the API."""
		type = type.lower()
		type = type if type[-1:] == "s" else type + "s"
		return self.client.objects.s(type).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error)).put()

	def console(self, command, session=None, sandboxed=None):
		"""Usage of the Icinga2 (API) console feature."""
		# TODO auto-completion is possible through a different URL endpoint
		query = self.client.console.s("execute-script").command(command).session(session).sandboxed(sandboxed)
		return query.post()

	# TODO implement configuration management (?)


class Host(Icinga2Object):
	"""Representation of a Icinga2 Host object."""
	@property
	def services(self):
		"""Get services of this host."""
		query = self._query.client.objects.services.filter("host.name==\"{}\"".format(self.name)).get
		return Icinga2Objects(query, cache_time=self._expiry)

	def action(self, action, **parameters):
		"""Process action for this host."""
		query = self._query.client.actions.s(action).filter("host.name==\"{}\"".format(self.name))
		for parameter, value in parameters.items():
			query = getattr(query, parameter)(value)
		return query.post()


class Hosts(Icinga2Objects):
	@property
	def one(self):
		if len(self) != 1:
			raise NotExactlyOne("Exactly one object required, found {}".format(len(self)))
		return Host(self._query, self[0]["name"], self.response)


class Service(Icinga2Object):
	@property
	def host(self):
		"""Get host to wich this service beongs to."""
		hostname = self["attrs"]["host_name"]
		return Host(self._query.client.objects.hosts.s(hostname), hostname, cache_time=self._expiry)

	def action(self, action, **parameters):
		"""Process action for this service."""
		query = self._query.client.actions.s(action)
		for parameter, value in parameters.items():
			query = getattr(query, parameter)(value)
		return query.post(service=self.name)


class Services(Icinga2Objects):
	@property
	def one(self):
		if len(self) != 1:
			raise NotExactlyOne("Exactly one object required, found {}".format(len(self)))
		return Service(self._query, self[0]["name"], self.response)


class Templates(Icinga2Objects):
	"""Representation of an Icinga2 templates."""
	def __init__(self, query, data=None, cache_time=60):
		super().__init__(query, data, cache_time=cache_time)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates


class Template(Icinga2Object):
	"""Representation of an Icinga2 template."""
	def __init__(self, query, name, data=None, cache_time=60):
		super().__init__(query, name, data, cache_time=cache_time)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates
