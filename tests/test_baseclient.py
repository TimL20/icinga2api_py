
from icinga2api_py import API


def get_pid(client):
    return client.status.IcingaApplication.get().json()["results"][0]["status"]["icingaapplication"]["app"]["pid"]


#######################################################################################################################
def test(host, username, password, **kwargs):
    client = API(host, (username, password), **kwargs)
    pid = get_pid(client)
    print("Icinga PID: {}".format(pid))


if __name__ == "__main__":
    test("icinga", "user", "pass")
