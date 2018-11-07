icinga2api_py
===============

Simple access to the Icinga2 API on top of Python [requests](https://github.com/requests/requests).

## What you can do with it
- Connect to the API with 
- Create objects
- Query objects, cached and with auto-(re)load
- Modify and delete objects of all types, also multiple objects at once
- Actions (acknowledge, ...), also for multiple objects at once
- If you don't use the OOP interface, then you should be able to do everything except streams

## What you can't do with it
- Using it without any knowledge of the Icinga2 API or the documentation for this package
- Any streams (EventStreams) are currently not supported
- ConfigurationManagement is not available via object oriented interface
- Some things (Console, ...) are not tested

## Usage examples for the object oriented interface

```
from icinga2api_py import Icinga2
# Connect client to Icinga2 API

# Get an instance representing the Icinga2 node, connected this node via API
icinga = Icinga2("icingahost", ("username", "passwd"))

# Get a host object representing localhost
localhost = icinga.objects.hosts.localhost.get()
if not localhost["attrs"]["state"]:  # if state is not up
    print("Icinga seems to think, that it could run, even if it has no host to run on...")

print("The host localhost has the following services:")
servicenames = [service["name"] for service in localhost.services]
print(", ".join(servicenames))
```
 