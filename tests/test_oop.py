
from icinga2api_py import Client
from icinga2api_py import Icinga2


def get_pid(icinga):
    return icinga.status.IcingaApplication.get().one["status"]["icingaapplication"]["app"]["pid"]


#######################################################################################################################
def test(host, username, password, cache_time, **kwargs):
    client = Client(host, (username, password), **kwargs)
    icinga = Icinga2(client, cache_time)
    pid = get_pid(icinga)
    print("Icinga PID: {}".format(pid))


if __name__ == "__main__":
    test("icinga", "user", "pass", 30)
