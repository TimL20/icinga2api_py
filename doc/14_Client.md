# Client
The class `icinga2api_py.Client` is a subclass of `API`, wich usage was described in "Basic API Client". The client
inherits everything from `API`, and does only change one thing: the response parser.
So everything stays the same, but you get parsed responses instead of the responses directly from requests.

## Response
Response, as returned from any request with the client, is a sequence customized for sucessfull responses of the
Icinga2 API. You can get the original requests response with the `response` property, but you can also directly get the
returned results of this response (`results` property), wich are already decoded.
Any response object acts like a presentation of these results. You can iterate through results, get a particular result
and so on, everything just with the response:
```
from icinga2api_py import Client
client = Client(host, (username, password))  # Create a client as with API

appstatus = client.status.IcingaApplication.get()  # Get a response object

pid = [0]["status"]["icingaapplication"]["app"]["pid"]  # Get something particular

# Get one response with every host
hosts = client.objects.hosts.get()
# Iterate over all hosts
for host in hosts:
    print("Host {} has state {}".format(host["name"], host["attrs"]["state"]))
```

The request is executed with calling the HTTP method (`get()` in these examples).

### Usefull methods
Response objects also have some usefull methods.

```
# I assume we have all variables from the previous example

# How much hosts does our monitoring know?
print("Our monitoring knows currently {} host(s)".format(len(hosts)))

# Print all host names (= get all name values)
print(", ".join(hosts.values("name")))

# Are all hosts down? (= have all attrs.state attributes the value 1)
if hosts.are_all("attrs.state", 1):
    print("Everything is down")

# Is minimum one host down (= has min. one attrs.state attribute the value 1)
if hosts.min_one("attrs.state", 1):
    print("At least one host is down")
```

### Everything else
Response has a `__getattr()__` method, redirecting every unknown attribute to it's self.response property. This is
usefull on errors ore similar:
```
hosts.ok  # True if request was successfull
hosts.json()  # Returns the bare JSON parsed request, usefull on errors
hosts.status_code  # HTTP response status code
```

These are just some examples. You usually won't - at least I won't - use these things as described above. But they are
fine, and the best thing is: they are also available when using the OOP interface (because of inheritance).
