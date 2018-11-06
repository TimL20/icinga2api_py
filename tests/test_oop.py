
from icinga2api_py import Client
from icinga2api_py import Icinga2


def get_pid(icinga):
    return icinga.status.IcingaApplication.get().one["status"]["icingaapplication"]["app"]["pid"]

def get_localhost(icinga):
    return icinga.objects.hosts.localhost.get()


#######################################################################################################################
def test(host, username, password, **kwargs):
    icinga = Icinga2(host, (username, password), **kwargs)

    pid = get_pid(icinga)
    print("Icinga PID: {}".format(pid))
    localhost = get_localhost(icinga)
    print("Localhost has state {}, type {}".format(localhost["attrs"]["state"], localhost["attrs"]["state_type"]))


if __name__ == "__main__":
    test("icinga", "user", "pass", cache_time=30)
