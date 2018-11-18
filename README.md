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

## Notice, that ...
- ... knowledge of the Icinga2 API is recommended
- ... the documentation is not ready. Actually it's more a collection of working examples than a documentation...
- ... any streams (EventStreams) are currently not supported
- ... ConfigurationManagement is not available via object oriented interface
- ... A few things (Console feature, ConfigurationManagement and more) are not tested

## Usage examples for the object oriented interface

```
from icinga2api_py import Icinga2
# Connect client to Icinga2 API

# Get an instance representing the Icinga2 node, connected this node via API
icinga = Icinga2("icingahost", ("username", "passwd"))

# Get a host object representing localhost
localhost = icinga.objects.hosts.localhost.get()
if not localhost["attrs.state"]:  # if state is not up
    print("The host 'localhost' seems to be down.")

print("The host localhost has the following services:")
servicenames = [service["name"] for service in localhost.services]
print(", ".join(servicenames))
```
 