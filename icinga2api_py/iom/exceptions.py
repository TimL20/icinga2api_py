# -*- coding: utf-8 -*-


class UnallowedOperationError(BaseException):
	"""Exception for all operations that are not allowed."""


class NoUserView(UnallowedOperationError):
	"""Exception for a get on a field with "no_user_view" attribute set to True."""


class NoUserModify(UnallowedOperationError):
	"""Exception for a get on a field with "no_user_modify" attrute set to True."""
