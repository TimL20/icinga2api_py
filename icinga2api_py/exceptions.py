# -*- coding: utf-8 -*-
"""This module contains exceptions."""


class InvalidIcinga2ApiResponseError(Exception):
	"""Raised, when there was an invalid response (according to the Icinga2 API documentation)."""
