# -*- coding: utf-8 -*-
"""Object oriented access to Icinga2 and it's objects over API.
"""

import logging
from .base_objects import Icinga2Objects, Icinga2Object


class Host(Icinga2Object):
	"""Representation of a Icinga2 Host object."""
	@property
	def services(self):
		"""Get services of this host."""
		try:
			return self._request.api.objects.services.filter("host.name==\"{}\"".format(self.name)).get()
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing services from a Host object.")


class Hosts(Icinga2Objects):
	pass  # TODO construct Host object for result


class Service(Icinga2Object):
	@property
	def host(self):
		"""Get host to wich this service beongs to."""
		try:
			hostname = self["attrs"]["host_name"]
			return self._request.api.objects.hosts.s(hostname).get(caching=self._expiry)
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing Host object from Service object.")


class Services(Icinga2Objects):
	pass  # TODO construct Service object for result


class Templates(Icinga2Objects):
	"""Representation of an Icinga2 templates."""
	def __init__(self, request, caching, response=None):
		super().__init__(request, caching, response)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates


class Template(Icinga2Object):
	"""Representation of an Icinga2 template."""
	def __init__(self, request, name, caching, response=None, data=None):
		super().__init__(request, name, caching, response, data)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates
