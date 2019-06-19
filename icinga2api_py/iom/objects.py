# -*- coding: utf-8 -*-
"""This module contains funcionality for all mapped objects.

The classes for the mapped Icinga objects are created in the types module, but every class created there inherits from
a class here.
No thread-safety (yet)."""

from .exceptions import NoUserView, NoUserModify
from ..results import Result, CachedResultSet
from .types import Number

# Possible keys of an objects query result
OBJECT_QUERY_RESULT_KEYS = {"name", "type", "attrs", "joins", "meta"}


class IcingaObjects(CachedResultSet):
	"""Representation, of any number of Icinga objects that have same type.
	This is the parent class of all dynamically created Icinga object type classes."""

	# The DESC is overriden in subclasses with the Icinga type description
	DESC = {}
	# The FIELDS is overriden in subclasses with all FIELDS and their description for the object type (incl. from parents)
	FIELDS = {}

	def __init__(self, session, request, response=None, results=None, next_cache_expiry=None):
		super().__init__(request, session.cache_time, response, results, next_cache_expiry)
		self._session = session

	def result(self, index):
		"""Return an object representation for the object at this index of results."""
		if isinstance(index, slice):
			# Return plural type for slice
			number = Number.PLURAL
		else:
			# Not a slice -> convert to slice for simplification
			index = slice(index, index + 1)
			# Return singular type
			number = Number.SINGULAR

		# Get results of the objects in this slice
		results = [super().result(i) for i in range(len(self))[index]]
		# Get names of the objects in this slice
		names = [res["name"] for res in results]
		# Construct a filter for these names
		# TODO check how that works for objects with composite names (e.g. services)
		filterstring = "{}.name==\"{}\"".format(self.type, "\" || {}.name==\"".format(self.type).join(names))

		# Copy query for these objects
		req = self._request.clone()
		req.json = dict(req.json)
		# Apply constructed filter and return the result of this query
		req.json["filter"] = filterstring
		class_ = self._session.types.type(self.type, number)
		# TODO check whether that works, I'm not sure
		return class_(self._session, req, results=results, next_cache_expiry=self._expires)

	@property
	def type(self):
		"""The type of this/these object(s). Always returns the singular name."""
		return self.DESC["name"]

	def parse_attrs(self, attrs):
		"""Parse attrs string.
		"attrs.state" -> ["attrs", "state"]
		"name" -> ["name"]
		"last_check_result.output" -> ["attrs", "last_check_result", "output"]

		Also on a <Type, e.g. host> object:
		"<typename>.last_check_result.output" -> ["attrs", "last_check_result", "output"]

		Also on a <Type> that is in the list of joins (looked up in the request):
		"<typename>.last_check_result.output" -> ["joins", <typename>, "last_check_result", "output"]
		"""
		split = attrs.split('.')

		# First key (name, type, attrs, joins, meta) - defaults to attrs
		if split[0] not in OBJECT_QUERY_RESULT_KEYS:
			# First key of attrs is not one that is handled "naturally"
			if split[0].lower() == self.type.lower():
				# Key is own type; cut first entry of split and insert "attrs" instead
				return ["attrs"] + split[1:]
			elif split[0] in self._request.json.get("joins", tuple()):
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

	def __setattr__(self, key, value):
		"""Modify object value(s) if the attribute name is a field of this object type. Otherwise default behavior."""
		attr = self.parse_attrs(key)  # Will possibly prefix "attrs"
		if attr[1] not in self.FIELDS:
			return super().__setattr__(key, value)

		if attr[0] == "joins":
			raise NoUserModify("Modification of a joined object is not supported.")
		elif attr[0] != "attrs":
			raise NoUserModify("Not allowed to modify attribute {}. Not an attribute.".format(key))
		else:
			# Modify this object
			self.modify({".".join(attr[1:]): value})

	def modify(self, attrs):
		"""Modify this/these objects. Attributes to modify as a dict."""
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

		if ret.status_code >= 400:
			# Something went wrong -> do not modify
			return ret

		# Modify cached attribute values
		for res in self.results:
			for key, value in attrs.items():
				res[self.parse_attrs(key)] = value

		return ret


class IcingaObject(Result, IcingaObjects):
	"""Representation of an Icinga object."""

	# The DESC is overriden in subclasses with the Icinga type description
	DESC = {}
	# The FIELDS is override in subclasses with all FIELDS and their description for the object type (incl. from parents)
	FIELDS = {}

	def __init__(self, session, request, response=None, results=None, next_cache_expiry=None):
		# Call other super init first
		IcingaObjects.__init__(self, session, request, response, results, next_cache_expiry)
		# Call super init of Result, overwrites results
		super().__init__(results)

	@property
	def name(self):
		"""The name of this object."""
		return self["name"]

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
			if split[0].lower() == self.type.lower():
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

	def __getitem__(self, item):
		"""Implements sequence and mapping access in one."""
		if isinstance(item, (int, slice)):
			super().__getitem__(item)

		# Mapping access
		attr = self.parse_attrs(item)
		if attr[0] == "attrs":
			# Check no_user_view
			if self.permissions(attr[1])[0]:
				raise NoUserView("Not allowed to view attribute {}".format(attr))
		# TODO handle dictionaries
		return super().__getitem__(attr)

	def __getattr__(self, attr):
		"""Get value of a field."""
		attr = self.parse_attrs(attr)
		if attr[0] == "attrs" and attr[1] not in self.FIELDS:
			raise AttributeError

		# Mapping access - let __getitem__ do the real work
		return self[attr]
