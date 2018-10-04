# -*- coding: utf-8 -*-
"""Representations of Icinga2 objects.
"""

import sys
import collections.abc
from .base import Icinga2Objects
from .base import Icinga2Object


class Icinga2:
	"""Object representing all general things of a Icinga2 instance (global variables, status, ...)"""
	def __init__(self, client):
		self.client = client

	@staticmethod
	def get_object(client, type, name):
		"""Get an object by it's type and name."""
		type = type.lower()
		# Special case(s)
		if type == Icinga2.__name__:
			return Icinga2(client)
		# In all other cases: get class for the specified type, and create an object of this class
		class_ = getattr(sys.modules[__name__], type.title(), None)
		type = type if type[-1:] == "s" else type + "s"
		if class_ is not None:
			return class_(client.objects.s(type).s(name).get, name)
		return Icinga2Object(client.objects.s(type).s(name).get, name)

	@staticmethod
	def get_objects(client, type, filter):
		"""Get an Icinga2Objects object by type and a filter. The given filter could be a filter string, a list of
		filter strings, or a collections.abc.Mapping wich will be converted to a (&&-connected) filter string."""
		filterstring = filter  # default that is ok for lists and strings
		if isinstance(filter, collections.abc.Mapping):
			filterlist = []
			for attribute, value in filter.items():
				filterlist.append("{}=={}".format(attribute, value))
			filterstring = " && ".join(filterlist)
		# Get class for specified type
		type = type.lower()
		class_ = getattr(sys.modules[__name__], type.title(), None)
		type = type if type[-1:] == "s" else type + "s"
		if class_ is not None:
			return class_(client.objects.s(type).filter(filterstring).get)
		return Icinga2Objects(client.objects.s(type).filter(filterstring).get)

	# implement actions here? (todo?)

	# implement configuration management here? (todo?)

	# implement console here? (todo?)


class Host(Icinga2Object):
	def __init__(self, query, name, data=None):
		super().__init__(query, name, data)

	# TODO add get services

	# TODO create / modify / delete


class Hosts(Icinga2Objects):
	def __init__(self, query, data=None):
		super().__init__(query, data)

	def _create_object(self, index):
		return Host.get_object(self._query.client, self._response[index]["name"])

	# TODO add actions (reschedule, ack, ..)


class Service(Icinga2Object):
	def __init__(self, query, name, data=None):
		super().__init__(query, name, data)

	# TODO create / modify / delete


class Services(Icinga2Objects):
	def __init__(self, query, data=None):
		super().__init__(query, data)

	# TODO add actions (reschedule, ack, ...)


class Hostgroup(Icinga2Object):
	pass  # TODO implement


class Hostgroups(Icinga2Objects):
	pass  # TODO implement


class Servicegroup(Icinga2Object):
	pass  # TODO implement


class Servicegroups(Icinga2Objects):
	pass  # TODO implement


class Template(Icinga2Object):
	pass  # TODO implement


class Templates(Icinga2Objects):
	pass  # TODO implement


class Downtime(Icinga2Object):
	pass  # TODO implement


class Downtimes(Icinga2Objects):
	pass  # TODO implement


class Notification(Icinga2Object):
	pass  # TODO implement


class Dependency(Icinga2Object):  # Plural?
	pass  # TODO implement


class User(Icinga2Object):
	pass  # TODO implement


class Usergroup(Icinga2Object):
	pass  # TODO implement


class Zone(Icinga2Object):
	pass  # TODO implement


class EventStream:
	pass  # TODO implement
