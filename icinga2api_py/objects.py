# -*- coding: utf-8 -*-
"""Object oriented access to Icinga2 and it's objects over API.
"""

import logging
import sys
import collections.abc
from .api import API
from .base import Client
from .base import StreamClient
from .base import NotExactlyOne
from .base import Icinga2Objects
from .base import Icinga2Object

# Where to find the object type and name for wich URL
TYPES_AND_NAMES = {
	"objects": (1, 2),  # /objects/<type>/<name>
	"templates": (0, 2),  # /templates/<temptype>/<name>
	"variables": (0, 1),  # /variables/<name>
}


def parse_filter(filter):
	if isinstance(filter, collections.abc.Mapping):
		filterlist = []
		for attribute, value in filter.items():
			filterlist.append("{}=={}".format(attribute, value))
		filter = " && ".join(filterlist)
	return filter


class Query:
	"""OOP interface helper class, to return an Icinga2Objects object with a prepared request on call."""
	def __init__(self, client, url, body, method):
		self.client = client
		self.url = url
		self.body = body
		self.method = method

	@property
	def request(self):
		return API.Request(self.client, self.url, self.body, self.method)

	def __call__(self, *args, **kwargs):
		# Find object type and maybe name in URL
		# Cut base url
		url = self.url[self.url.find(self.client.base_url)+len(self.client.base_url):]
		# Split by /
		url = "" if not url else url.split("/")
		basetype = url[0]
		if basetype in TYPES_AND_NAMES:
			# Information about type and name in URL is known
			type_ = url[TYPES_AND_NAMES[basetype][0]]
			namepos = TYPES_AND_NAMES[basetype][1]
			name = url[namepos] if len(url) > namepos > 0 else None
		else:
			# Default type guessing
			type_ = basetype
			name = None
		# Cut last letter of plural form
		type_ = type_[:-1] if name is not None and type_[-1:] == "s" else type_
		logging.getLogger(__name__).debug("Assumed type %s and name %s from URL %s", type_, name, self.url)

		if "name" in kwargs:
			name = kwargs["name"]
			del kwargs["name"]

		return self.client.object_from_query(type_, self.request, name, **kwargs)


class Icinga2(Client):
	"""Central class of this OOP interface for the Icinga2 API.
	An object of this class is needed for a lot of things of the OOP interface."""
	def __init__(self, host, auth=None, port=5665, uri_prefix='/v1', cache_time=60, **sessionparams):
		self.cache_time = cache_time
		self.sessionparams = sessionparams  # It's kind of a workaround to create a "real" Client
		super().__init__(host, auth, port, uri_prefix, **sessionparams)
		self.Request = Query

	@property
	def client(self):
		"""Get non-OOP interface client."""
		# Create client with None for all base_url things
		client = Client(None, self.auth, None, None, **self.sessionparams)
		client.base_url = self.base_url
		return client

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

	def create_object(self, type, name, attrs, templates=tuple(), ignore_on_error=False):
		"""Create an Icinga2 object through the API."""
		type = type.lower()
		type = type if type[-1:] == "s" else type + "s"
		return self.client.objects.s(type).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error)).put()  # Fire request immediately

	def console(self, command, session=None, sandboxed=None):
		"""Usage of the Icinga2 (API) console feature."""
		# TODO auto-completion is possible through a different URL endpoint
		query = self.client.console.s("execute-script").command(command).session(session).sandboxed(sandboxed)
		return query.post()

	# TODO implement configuration management (?)


class Host(Icinga2Object):
	"""Representation of a Icinga2 Host object."""
	def __getattr__(self, item):
		print("Host __getattr__")

	@property
	def services(self):
		"""Get services of this host."""
		try:
			query = self._query.api.client.objects.services.filter("host.name==\"{}\"".format(self.name)).get
			return Services(query, cache_time=self._expiry)
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing services from a Host object.")


class Hosts(Icinga2Objects):
	@property
	def one(self):
		try:
			if len(self) != 1:
				raise NotExactlyOne("Exactly one object required, found {}".format(len(self)))
			return Host(self._query, self[0]["name"], self.response)
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing one Host from Hosts.")


class Service(Icinga2Object):
	@property
	def host(self):
		"""Get host to wich this service beongs to."""
		try:
			hostname = self["attrs"]["host_name"]
			return self._query.api.objects.hosts.s(hostname).get(cache_time=self._expiry)
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing Host object from Service object.")


class Services(Icinga2Objects):
	@property
	def one(self):
		try:
			if len(self) != 1:
				raise NotExactlyOne("Exactly one object required, found {}".format(len(self)))
			return Service(self._query, self[0]["name"], self.response)
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing one Service from Services.")


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
