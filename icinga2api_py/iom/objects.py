# -*- coding: utf-8 -*-
"""This module contains funcionality for all mapped objects.

The classes for the mapped Icinga objects are created in the types module, but every class created there inherits from
a class here.
No thread-safety (yet)."""

from .exceptions import NoUserView, NoUserModify
from ..results import CachedResultSet


class IcingaObject(CachedResultSet):
	"""Representation of an Icinga object."""

	# The DESC is overriden in subclasses with the Icinga type description
	DESC = {}
	# The FIELDS is override in subclasses with all FIELDS and their description for the object type (incl. from parents)
	FIELDS = {}

	def __init__(self, session, request):
		super().__init__(request, session.cache_time)
		self._session = session

	def permissions(self, attr):
		"""Get permission for a given attribute (field), returned as a tuple for the boolean values of:
		no_user_view, no_user_modify
		All values True is the default."""
		try:
			field = self.FIELDS[attr]["attributes"]
		except KeyError:
			field = {"attributes": {"no_user_view": True, "no_user_modify": True}}
		return field.get("no_user_view", True), field.get("no_user_modify", True)

	def __getattr__(self, attr):
		if attr in self.FIELDS:
			# Check no_user_view
			if self.permissions(attr)[0]:
				raise NoUserView("Not allowed to view attribute {}".format(attr))
			# TODO refactor that later (?)
			# TODO how to reach joins now?
			# TODO explicit type instead of attrs? (would solve joins problem)
			return self[0]["attrs"][attr]

		# attribute not in fields
		raise AttributeError

	def __setattr__(self, key, value):
		if key not in self.FIELDS:
			return super().__setattr__(key, value)

		# Modify this object
		self.modify({key: value})

	def modify(self, attrs):
		"""Modify this object. Attributes to modify as a dict."""
		# Check if modification is allowed
		for key in attrs.keys():
			if self.permissions(key)[1]:
				raise NoUserModify("Not allowed to modify attribute {}".format(key))

		# Create modification query
		mquery = self._request.clone()
		mquery.method_override = "POST"
		# Copy original JSON body and overwrite attributes for modification
		mquery.json = dict(mquery.json)["attrs"] = {}
		mquery.json["attrs"] = attrs
		# Fire modification query (returns APIResponse object)
		ret = mquery()

		if not ret.ok:
			# Something went wrong -> do not modify
			return ret

		# Modify cached attribute values
		for key, value in attrs.items():
			# TODO refactor that later (?) (maybe no "attrs"?)
			self._results[0]["attrs"][key] = value

		return ret
