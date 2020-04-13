# -*- coding: utf-8 -*-
"""This module contains exceptions."""


class Icinga2ApiError(ValueError):
	"""Base class for all API-related errors in this package."""


class InvalidIcinga2ApiResponseError(Icinga2ApiError):
	"""Raised, when there was an invalid response (according to the Icinga2 API documentation)."""


class ParsingError(ValueError):
	"""Error on parsing some input."""


class AttributeParsingError(ParsingError):
	"""Error when parsing an attribute description."""


class FilterParsingError(ParsingError):
	"""Error on parsing a filter string."""


class LiteralExecutionError(RuntimeError):
	"""Error when executing an Icinga literal locally, in which case it's propably not possible to execite the literal
	locally."""


class FilterExecutionError(LiteralExecutionError):
	"""Error when executing a filter locally, in which case it's propably not possible to execute the filter locally."""
