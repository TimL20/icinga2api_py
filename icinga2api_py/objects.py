# -*- coding: utf-8 -*-
"""Representations of Icinga2 objects.
"""

import sys
import collections.abc
from .base import Icinga2Objects
from .base import Icinga2Object


class Icinga2:
	"""Object representing all general things of a Icinga2 instance (global variables, status, ...)"""
	def __init__(self, client, cache_time=60):
		self.client = client
		self.cache_time = cache_time

	def get(self, query_base, type, query_end, name=None):
		"""Get a appropriate python object to represent whatever is queried with the query.
		The query is built in this method, with query_base as start, then the type, then the query_end.
		This method assumes, that a named object is singular (= one object). The name is not used for building the query,
		but it's passed to any Icinga2Object constructor.
		This method is usually used by other methods of this class."""
		type = type.lower()
		# Special case(s)
		if type == Icinga2.__name__:
			return Icinga2(self.client, self.cache_time)
		class_ = getattr(sys.modules[__name__], type.title(), None)
		initargs = {"cache_time": self.cache_time}
		singular = name is not None  # it's one object if it has a name
		if singular:
			initargs["name"] = name
			type = type + "s"  # for query building
		query = query_base.s(type)
		if query_end is not None:
			for i in query_end:
				query = getattr(query, i, None)
		if class_ is not None:
			return class_(query.get, **initargs)
		return Icinga2Object(query.get, **initargs)

	def get_object(self, type, name):
		"""Get an object by it's type and name."""
		return self.get(self.client.objects, type, name, name)

	def get_objects(self, type, filter):
		"""Get an Icinga2Objects object by type and a filter. The given filter could be a filter string, a list of
		filter strings, or a collections.abc.Mapping wich will be converted to a (&&-connected) filter string."""
		filterstring = filter  # default that is ok for lists and strings
		if isinstance(filter, collections.abc.Mapping):
			filterlist = []
			for attribute, value in filter.items():
				filterlist.append("{}=={}".format(attribute, value))
			filterstring = " && ".join(filterlist)
		return self.get(self.client.objects.filter(filterstring), type, None)

	def create_object(self, type, name, templates, attrs, ignore_on_error):
		type = type.lower()
		type = type if type[-1:] == "s" else type + "s"
		return self.client.objects.s(type).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error))

	# implement actions here? (todo?)

	# implement configuration management here? (todo?)

	# implement console here? (todo?)


class Host(Icinga2Object):
	@property
	def services(self):
		query = self._query.client.objects.services.filter("host.name==\"{}\"".format(self.name)).get
		return Services(query, cache_time=self._expiry)

	# TODO add actions (reschedule, ack, ..)


class Hosts(Icinga2Objects):
	def _create_object(self, index):
		return Host.get_object(self._query.client, self._response[index]["name"])

	# TODO add actions (reschedule, ack, ..)


class Service(Icinga2Object):
	@property
	def host(self):
		hostname = self["attrs"]["host_name"]
		return Host(self._query.client.objects.hosts.s(hostname), hostname, cache_time=self._expiry)

	# TODO add actions (reschedule, ack, ..)


class Services(Icinga2Objects):
	pass
	# TODO add actions (reschedule, ack, ...)


class Hostgroup(Icinga2Object):
	pass  # TODO implement


class Hostgroups(Icinga2Objects):
	pass  # TODO implement


class Servicegroup(Icinga2Object):
	pass  # TODO implement


class Servicegroups(Icinga2Objects):
	pass  # TODO implement


class EventStream:
	pass  # TODO implement


class Templates(Icinga2Objects):
	def __init__(self, query, data=None, cache_time=60):
		super().__init__(query, data, cache_time=cache_time)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates

	# Templates and events seem to have similarities, is it possible to unite them??? (todo?)


class Template(Icinga2Object):
	def __init__(self, query, name, data=None, cache_time=60):
		super().__init__(query, name, data, cache_time=cache_time)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates


