# -*- coding: utf-8 -*-
"""This (sub-)package contains everything for Icinga-object-mapping access over the Icinga API.

The idea is, that every object in Icinga is mapped to a Python object.
An object of Icinga means everything, that is accessable over the /objects endpoint of the Icinga API.
The information for the type and its fields is gathered from the /types endpoint of the API. There is supposed to be a
Python class for every (not trivial mapable) Icinga object type. This funcitonality is done by the types module.
The object mapping access should also be capable of modifying objects as known from ORM frameworks. Such functionality,
as well as getting the objects from Icinga, is done by the objects module."""

from .types import Types
from .session import Session
