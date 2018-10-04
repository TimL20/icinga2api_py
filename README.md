icinga2api_py
===============

Icinga2 API routines in/for python, general usage.

## What you can do with it
- Create, modify and delete objects of all types
- Query objects, cached and with auto-(re)load
- Actions (acknowledge, ...)
- Receive event streams

## What you can't do with it
- Use it without knowledge of the API or at least the documentation for this package
 (but the documentation does not exist, so I doubt that someone is able to read it)
 
 ## Usage examples
 ### Usage of underlying API Client
 There are three API Clients in this package. One is the most basic thing in this package. The API Clients are just 
 kind of a wrapper around requests, and return data as they get it from the Icinga2 API (via requests). That why, this 
 client is able to do everything the API you could do manually.
 ```
from icinga2api_py import API
client = API("localhost", ("user", "pass"))
icinga_pid = client.status.IcingaApplication.get().json()["results"][0]["status"]["icingaapplication"]["app"]["pid"]

response = client.objects.services.joins(["host.state"]).attrs("name", "state").filter("host.name==\"localhost\"").get()

client.actions.s("reschedule-check").filter("service.name==\"ping4\" && host.name==\"localhost\"").type("Service").post()
```

### Usage of proper API Client(s)
Requests are exactly the same as with the basic API Client, but the responses are parsed. The returned objects are 
iterable usually sequences.
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

There is a StreamClient with focus on the Icinga2 API feature "EventStream". Note: I haven't tested this feature yet.
```
from icinga2api_py import StreamClient
# Connect client to Icinga2 API
client = StreamClient("icingahost", ("username", "passwd"))
stream = client.events.types(["StateChange"]).queue("queuename").post()  # I don't know why it's post...
first_response = next(stream.iter_responses())
print("First response: {}".format(first_response))
```

### Usage of OOP interface
Currently the OOP interface is capable of querying Icinga2 objects, querying templates, querying variables, querying 
status and statistics, process actions. Maybe it is also possible to use the console and read an event stream, but I 
haven't tried that yet. As it's maybe clearly visible: the focus lies a bit more on querying than on everything else.
The reason is simply, that querying is the reason I started to write this package for...
```
from icinga2api_py import Client
from icinga2api_py import Icinga2
# Connect client to Icinga2 API
client = Client("icingahost", ("username", "passwd"))

# Get an instance representing the Icinga2 node, to wich the client is connected to
icinga = Icinga2(client)

localhost = icinga.get_object("host", "localhost")  # query the host localhost
if not localhost["attrs"]["state"]:  # if state is not up
    print("Icinga seems to think, that it could run, even if it has no host to run on...")
    sys.exit()
services = localhost.services
 ```
 