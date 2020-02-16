# -*- coding: utf-8 -*-
"""Object oriented access to Icinga2 and it's objects over API.
"""

import logging
from ..simple_oo.base_objects import Icinga2Objects, Icinga2Object, ActionMixin


class Host(Icinga2Object, ActionMixin):
	"""Representation of a Icinga2 Host object."""
	@property
	def services(self):
		"""Get services of this host."""
		try:
			return self._request.api.objects.services.filter("host.name==\"{}\"".format(self.name)).get()
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing services from a Host object.")


class Hosts(Icinga2Objects, ActionMixin):
	"""Representation of Icinga2 host objects."""
	def result(self, index):
		"""Return a Host object at this index."""
		return self.result_as(index, Host)


class Service(Icinga2Object, ActionMixin):
	"""Representation of an Icinga2 Service object."""
	@property
	def host(self):
		"""Get host to wich this service beongs to."""
		try:
			hostname = self["attrs"]["host_name"]
			return self._request.api.objects.hosts.s(hostname).get()
		except AttributeError:
			logging.getLogger(__name__).exception("Exception constructing Host object from Service object.")


class Services(Icinga2Objects, ActionMixin):
	def result(self, index):
		"""Return a Service object at this index."""
		return self.result_as(index, Service)


class Templates(Icinga2Objects):
	"""Representation of Icinga2 templates."""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates

	def result(self, index):
		"""Return a Template object at this index."""
		return self.result_as(index, Template)


class Template(Icinga2Object):
	"""Representation of an Icinga2 template."""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.modify = None  # Not supported for templates
		self.delete = None  # Not supported for templates
