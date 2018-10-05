# -*- coding: utf-8 -*-
"""OOP access to Icinga2 and it's objects.
"""

import sys
import collections.abc
from .base import StreamClient
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
	An object of this class is needed for almost everything."""
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
		class_ = getattr(sys.modules[__name__], type.title(), None)
		initargs = {"cache_time": self.cache_time}
		singular = name is not None  # it's one object if it has a name
		if singular:
			initargs["name"] = name
			type = type + "s"  # for query building
		query = query_base.s(type)
		if query_end is not None:
			query_end = [query_end] if isinstance(query_end, str) else query_end
			for i in query_end:
				query = getattr(query, i)
		if class_ is not None:
			return class_(query.get, **initargs)
		if singular:
			return Icinga2Object(query.get, **initargs)
		return Icinga2Objects(query.get, **initargs)

	def get_object(self, type, name):
		"""Get an object by it's type and name."""
		return self.get(self.client.objects, type, name, name)

	def get_objects(self, type, filter):
		"""Get an Icinga2Objects object by type and a filter. The given filter could be a filter string, a list of
		filter strings, or a collections.abc.Mapping wich will be converted to a (&&-connected) filter string."""
		return self.get(self.client.objects.filter(parse_filter(filter)), type, None)

	def create_object(self, type, name, templates, attrs, ignore_on_error=False):
		"""Create an Icinga2 object through the API."""
		type = type.lower()
		type = type if type[-1:] == "s" else type + "s"
		return self.client.objects.s(type).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error)).put()

	def get_templates(self, object_type, filter=None):
		"""Get Icinga2 templates for a specified object type."""
		return self.get(self.client.filter(parse_filter(filter)), "templates", object_type)

	def get_template(self, object_type, name):
		"""Get an Icinga2 template by object type and name."""
		return self.get(self.client, "templates", [object_type, name])

	def get_variables(self, filter=None):
		"""Get Icinga2 variables."""
		return self.get(self.client.filter(parse_filter(filter)), "variables", None)

	def get_variable(self, name):
		"""Get an Icinga2 variable by name."""
		return self.get(self.client, "variables", name)

	@property
	def status(self):
		"""Query status information and statistics of Icinga2."""
		return self.get_status(None)

	def get_status(self, status_type=None):
		"""Get status information and statistics of Icinga2."""
		return self.get(self.client, "status", status_type)

	def action(self, action, filter=None, **parameters):
		"""Process a action (for example "acknowledge-problem")."""
		query = self.client.actions.s(action).filter(parse_filter(filter))
		for parameter, value in parameters.items():
			query = getattr(query, parameter)(value)
		return query.post()

	def get_stream(self, *url, **parameters):
		"""Get a stream response from the specified URL endpoint and pass parameters for that."""
		client = StreamClient.create_from_client(self.client)
		query = client
		for path in url:
			query = query.s(path)
		for parameter, value in parameters.items():
			query = query.s(parameter)(value)
		return query.post()

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
