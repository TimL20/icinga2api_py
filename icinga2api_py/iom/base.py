# -*- coding: utf-8 -*-
"""Some things that don't fit into other modules (or risk a circular import)."""

import enum


class Number(enum.Enum):
	"""Whether a type should be in singular or plural form. Or not specified (irrelevant)."""
	SINGULAR = 1
	PLURAL = 2
	IRRELEVANT = 0
