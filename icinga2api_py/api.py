# -*- coding: utf-8 -*-
"""
Small client for easy access to the Icinga2 API using the requests library
(https://github.com/psf/requests).

This client is really dump and has not much ideas about how the Icinga2 API works.
What it does is to set up a requests.Session (which it extends), build URL and body, construct request and a response
at the end. By default the constructed request is a :class:`icinga2api_py.models.APIRequest`, and the constructed
response a :class:`icinga2api_py.models.APIResponse`. It's possible to override these defaults in a subclass.
"""

import requests
from typing import Union

from .models import APIRequest, APIResponse

# Default request class
DEFAULT_REQUEST_CLASS = APIRequest
# Default response class
DEFAULT_RESPONSE_CLASS = APIResponse


class API(requests.Session):
	"""API session for easily sending requests and getting responses.

	Objects of this class are used for constructing a request, that than will use it's :meth:`prepare_request` and
	:meth:`create_response` methods for sending the request and constructing the response.
	The preparation method is inherited from the requests.Session superclass.
	"""

	#: Accepted HTTP methods (in a class attribute to enable easy overwriting).
	#: Everything else is a URL or body part for the :class:`RequestBuilder`
	HTTP_METHODS = {"GET", "POST", "PUT", "DELETE"}

	def __init__(self, url: str, **sessionparams):
		"""Construct the API session with an URL and "optional" session parameters.

		:param url: URL, e.g. "https://icingahost:5665/v1/", see :meth:`prepare_base_url` for what is expected here
		:param **sessionparams: Keyword arguments are set as session attribute. Every attribute of a requests.Session
					is allowed, these include: headers (default headers), auth, proxies, params (default
					parameters), verify, cert (client certificate path), trust_env and more.
		"""
		super().__init__()
		self.base_url = self.prepare_base_url(url)

		# Set default Accept header to JSON, as the Icinga2 API uses that
		self.headers["Accept"] = "application/json"

		# Set session parameters like verify, proxies, auth, ...
		for key, value in sessionparams.items():
			setattr(self, key, value)

	@staticmethod
	def prepare_base_url(url: str) -> str:
		"""Prepare the base_url for usage.

		This static method adds scheme, trailing '/', API version suffix and Icinga port defaults if not specified.
		This method is called by :meth:`__init__`.

		:param url: The URL to prepare for client usage
		:raises ValueError: if the url parameter is False in a boolean context
		:return: The prepared base URL
		"""
		if not url:
			raise ValueError(f"Unable to prepare URL {url}")
		# Prefix https if not specified
		if "://" not in url:
			url = f"https://{url}"
		# Append '/' to URL if not already there
		if url[-1:] != "/":
			url = f"{url}/"
		# Suffix API version
		if url[-3:-2] != "v":
			url = f"{url}v1/"
		# Set port if not specified
		scheme, _, host, path = url.split('/', 3)
		if ":" not in host:
			url = f"{scheme}//{host}:5665/{path}"

		return url

	@property
	def request_class(self):
		"""The class used as a request.

		This property is expected to return a callable, that acts like :class:`icinga2api_py.models.APIRequest`.
		It's usually only used internally, overwriting it in subclasses enables to easily change client behavior.
		"""
		return DEFAULT_REQUEST_CLASS

	def create_response(self, response):
		"""Create a custom response from a requests.Response."""
		return DEFAULT_RESPONSE_CLASS(response)

	@classmethod
	def from_pieces(cls, host, port=5665, url_prefix='/v1', **sessionparams) -> "API":
		"""Simplified creation of an API object."""
		url = f"https://{host}:{port}{url_prefix}/"
		return cls(url, **sessionparams)

	@classmethod
	def clone(cls, obj: "API") -> "API":
		"""Clone the given client.

		The returned object is something like a shallow copy of the given obj, but only attributes usually used with
		this class are copied. That this method will return a shallow copy comes with the possibly unwanted effected
		that e.g. updating headers for the clone also updates the headers of the original object. Attribute assignments
		will have no effect on clone objects of course.
		"""
		sessionparams = {}
		for attr in obj.__attrs__:
			sessionparams[attr] = getattr(obj, attr, None)
		api = cls(obj.base_url, **sessionparams)
		return api

	def __copy__(self):
		"""Get a shallow copy."""
		return self.clone(self)

	def __getattr__(self, item) -> "RequestBuilder":
		"""Return a RequestBuilder object with the given first item."""
		return self.s(item)

	def s(self, item) -> "RequestBuilder":
		"""Return a RequestBuilder object with the given first item."""
		return self.RequestBuilder(self).s(item)

	def __truediv__(self, item) -> "RequestBuilder":
		"""Return a RequestBuilder object with the given first item."""
		return self.RequestBuilder(self).s(item)

	class RequestBuilder:
		"""Class to build a request and it's dictionary (JSON) body."""

		def __init__(self, api: "API"):
			"""The RequestBuilder needs an API client object to init, mainly to pass it on to the request class."""
			self.api_client = api
			self._lastattr = None  # last attribute -> call to put in body, or not to add it to the URL
			self._builder_list = []  # URL Builder, joined with "/" at the and
			self._body = {}  # Request body as dictionary

		def _rotate_attr(self, new=None) -> "API.RequestBuilder":
			"""Helper method, as this functionality is needed twice.

			The "last used attr" is rotated. If nothing was done with the last used attr yet, it's added to the URL
			builder list. A new last used attr is set if given.
			"""
			if self._lastattr is not None:
				self._builder_list.append(self._lastattr)
				self._lastattr = None
			if new is not None:
				self._lastattr = new
			return self

		def __getattr__(self, item) -> Union[APIRequest, "API.RequestBuilder"]:
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			return self.s(item)

		def __truediv__(self, item) -> Union[APIRequest, "API.RequestBuilder"]:
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			return self.s(item)

		def s(self, item) -> Union[APIRequest, "API.RequestBuilder"]:
			"""Add item to URL path OR prepare item for put in body OR construct a request."""
			if item.upper() not in self.api_client.HTTP_METHODS:
				return self._rotate_attr(item)

			# item was a accepted HTTP method -> construct a request
			self._rotate_attr()
			# Construct URL with base url from api client + the "/"-joined builder list
			url = self.api_client.base_url + "/".join(self._builder_list)
			return self.api_client.request_class(self.api_client, item.upper(), url, json=self._body)

		def __call__(self, *args, **kwargs) -> "API.RequestBuilder":
			"""Call this object to put the last item into the body.

			The last item is put into the JSON-encoded body as a key, with the arguments this is called with as its
			value(s).
			Passing one argument causes this argument to be the value. When passing multiple arguments, the value is a
			list of these arguments. When no arguments are passed, the body value for this key is deleted.
			Things are a bit different, when the body already has a value with such a key.
			If a single arg gets passed and a single arg already is the value, the value gets a list of these two.
			If a single arg gets passed and the value has already multiple args, the new arg gets appended to the value.
			If multiple args are passed and there is a value, the value gets a list of all (args and value list items).
			"""
			key = self._lastattr
			# Reset last used attr
			self._lastattr = None

			single_item_exists = key in self._body and not isinstance(self._body[key], list)
			item_list_exists = key in self._body and isinstance(self._body[key], list)

			if len(args) == 1:
				# Exactly one arg given
				value = args[0]
				if single_item_exists:
					# Single item + single item => list
					self._body[key] = [self._body[key], value]
				elif item_list_exists:
					# Add single item to multiple existing items
					self._body[key] += (value, )
				else:
					# Set single item
					self._body[key] = value
			elif len(args) > 1:
				# More than one arg given
				value = list(args)
				if single_item_exists:
					# Add multiple items to single item
					self._body[key] = [self._body[key]] + value
				elif item_list_exists:
					# Add multiple items to multiple items
					self._body[key] += value
				else:
					# Set multiple items
					self._body[key] = value
			else:
				# No arg given -> delete
				del self._body[key]

			return self
