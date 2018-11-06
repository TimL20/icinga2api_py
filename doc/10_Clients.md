### Usage of basic API Client
There are three API Clients in this package. API Client (api.API) is just a kind of a wrapper around requests, and 
returns data as received from the Icinga2 API (via requests). That why, this client is able to do everything you can do 
with standard python and requests (and that should be almost everything the API is able to do).
An exception are streams, wich are not supported by this basic API client.

```
from icinga2api_py import API
client = API("icingahost", ("user", "pass"))
icinga_pid = client.status.IcingaApplication.get().json()["results"][0]["status"]["icingaapplication"]["app"]["pid"]

response = client.objects.services.joins(["host.state"]).attrs("name", "state").filter("host.name==\"localhost\"").get()

client.actions.s("reschedule-check").filter("service.name==\"ping4\" && host.name==\"localhost\"").type("Service").post()
```

### Usage of proper API Client(s)
Requests are exactly the same as with the basic API Client, but the responses are parsed. The returned objects are 
iterable sequences.

```
from icinga2api_py import Client
# Connect client to Icinga2 API
client = Client("icingahost", ("username", "passwd"))

icinga_pid = client.status.IcingaApplication.get()[0]["status"]["icingaapplication"]["app"]["pid"]

services = client.objects.services.attrs("name", "state").filter("host.name==\"localhost\"").get()
print("Host has {} services".format(len(services)))
if services.are_all("attrs.state", 0):
    print("All services are in OK state!")
for service in services:
    print("Service {} has state {}".format(service["name"], service["attrs"]["state"]))
```

There is a StreamClient with focus on the Icinga2 API feature "EventStream". But it does not work yet.

```
from icinga2api_py import StreamClient
# Connect client to Icinga2 API
client = StreamClient("icingahost", ("username", "passwd"))
stream = client.events.types(["StateChange"]).queue("queuename").post()
first_response = next(stream.iter_responses())
print("First response: {}".format(first_response))
```