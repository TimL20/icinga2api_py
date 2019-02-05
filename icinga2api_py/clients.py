# -*- coding: utf-8 -*-
"""This module will contain almost all of the different Icinga2 API clients."""

from .api import API
from .models import Query, APIResponse
from .results import ResultsFromResponse
from .base_objects import Icinga2Objects, Icinga2Object
from . import objects


class Client(API):
	"""Icinga2 API client for non-streaming content, without objects."""
	def __init__(self, url, **sessionparams):
		super().__init__(url, **sessionparams)

	@staticmethod
	def create_response(response):
		"""Return ResultSet with APIResponse with given response."""
		return ResultsFromResponse(APIResponse(response))


class Icinga2(API):
	"""A client for the object oriented part."""
	def __init__(self, url, caching=float("inf"), **sessionparams):
		super().__init__(url, **sessionparams)
		self.caching = caching
		self.request_class = Query
		self._client = None

	@property
	def client(self):
		"""Get non-OOP interface client. This is done by calling clone() of super()."""
		# TODO this should be a method rather than a property
		return API.clone(self)

	def object_from_query(self, type_, request, name=None, **kwargs):
		"""Get a appropriate python object to represent whatever is requested with the request.
		This method assumes, that a named object is singular (= one object). The name is not used.
		Remaining kwargs are passed to the constructor (Icinga2Object, Host, ...)."""
		class_ = getattr(objects, type_.title(), None)
		# Todo cut s of plural form if name is not None
		initargs = {"caching": self.caching}
		if name is not None:
			initargs["name"] = name
		initargs.update(kwargs)
		if class_ is not None:
			return class_(request, **initargs)
		if name is not None:
			# it's one object if it has a name
			return Icinga2Object(request, **initargs)
		return Icinga2Objects(request, **initargs)

	def create_object(self, type_, name, attrs, templates=tuple(), ignore_on_error=False):
		"""Create an Icinga2 object through the API."""
		# TODO maybe with python objects?
		type_ = type_.lower()
		type_ = type_ if type_[-1:] == "s" else type_ + "s"
		return self.client.objects.s(type_).s(name).templates(list(templates)).attrs(attrs)\
			.ignore_on_error(bool(ignore_on_error)).put()  # Fire request immediately

	def console(self, command, session=None, sandboxed=None):
		"""Usage of the Icinga2 (API) console feature."""
		# TODO auto-completion is possible through a different URL endpoint
		query = self.client.console.s("execute-script").command(command).session(session).sandboxed(sandboxed)
		return query.post()

	# TODO implement configuration management (?)
