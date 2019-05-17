# -*- coding: utf-8 -*-
"""This module contains funcionality for all mapped objects.

The classes for the mapped Icinga objects are created in the types module, but every class created there inherits from
a class here.
No thread-safety (yet)."""

from .exceptions import NoUserView, NoUserModify
from ..results import CachedResultSet
from ..results import OBJECT_QUERY_RESULT_KEYS


class IcingaObject(CachedResultSet):
	"""Representation of an Icinga object."""

	# The DESC is overriden in subclasses with the Icinga type description
	DESC = {}
	# The FIELDS is override in subclasses with all FIELDS and their description for the object type (incl. from parents)
	FIELDS = {}

	def __init__(self, session, request):
		super().__init__(request, session.cache_time)
		self._session = session

	def parse_attrs(self, attrs):
		"""Parse attrs string.
		"attrs.state" -> ["attrs", "state"]
		"name" -> ["name"]
		"last_check_result.output" -> ["attrs", "last_check_result", "output"]

		Also on a <Type, e.g. host> object:
		"<typename>.last_check_result.output" -> ["attrs", "last_check_result", "output"]

		Also on a <Type> that is in the joins dictionary:
		"<typename>.last_check_result.output" -> ["joins", <typename>, "last_check_result", "output"]
		"""
		split = attrs.split('.')
		# First key (name, type, attrs, joins, meta) - defaults to attrs

		if split[0] not in OBJECT_QUERY_RESULT_KEYS:
			# First key of attrs is not one that is handled "naturally"
			if split[0].lower() == self[0]["type"].lower():
				# Key is own type; cut first entry of split and insert "attrs" instead
				return ["attrs"] + split[1:]
			elif split[0] in self[0]["joins"]:
				# Type in joins
				return ["joins"] + split
			else:
				# Default is to insert "attrs" at the start
				return ["attrs"] + split
		# else
		return split

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
		attr = self.parse_attrs(attr)
		if attr[0] == "attrs" and attr[1] not in self.FIELDS:
			raise AttributeError

		if attr[0] == "attrs":
			# Check no_user_view
			if self.permissions(attr[1])[0]:
				raise NoUserView("Not allowed to view attribute {}".format(attr))
		return self[0][attr]

	def __setattr__(self, key, value):
		# TODO handle everything __getattr__ also handles, e.g. without "attrs" prefix
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
			self._results[0][self.parse_attrs(key)] = value

		return ret
