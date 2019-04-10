#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from icinga2api_py import StreamClient
from icinga2api_py import ResultList


def get_5res(client):
	ret = ResultList()
	# In with block to close stream (connection) after getting the results
	with client.events.types(["CheckResult"]).queue("abcdefg").post() as stream:
		for res in stream:
			ret.append(res)
			if len(ret) > 4:
				return ret


#######################################################################################################################
def test(host, username, password, **kwargs):
	client = StreamClient.from_pieces(host, auth=(username, password), **kwargs)
	for res in get_5res(client):
		print("Got check result: {}".format(res["check_result"]))


if __name__ == "__main__":
	test("icinga", "user", "pass")
