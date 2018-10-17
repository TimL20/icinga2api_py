icinga2api_py
===============

Icinga2 API routines in/for python, general usage.

## What you can do with it
- Create objects
- Query objects, cached and with auto-(re)load
- Modify and delete objects of all types, also multiple objects at once
- Actions (acknowledge, ...), also for multiple objects at once

## What you can't do with it
- Use it without any knowledge of the Icinga2 API or the documentation for this package
 (but the documentation is not ready to read yet...)
- EventStreams are currently not supported
- ConfigurationManagement and console might work, or might not work...
 
## Usage examples for OOP interface

```
from icinga2api_py import Client
from icinga2api_py import Icinga2
# Connect client to Icinga2 API
client = Client("icingahost", ("username", "passwd"))

# Get an instance representing the Icinga2 node, to wich the client is connected to
icinga = Icinga2(client)

localhost = icinga.objects.hosts.localhost.get()  # query the host localhost
if not localhost["attrs"]["state"]:  # if state is not up
    print("Icinga seems to think, that it could run, even if it has no host to run on...")
    sys.exit()
services = localhost.services
```
 