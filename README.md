icinga2api_py
===============

Icinga2 API routines in/for python, general usage.

## What you can do with it
- Create, modify and delete objects of all types
- Query objects, cached and with auto-(re)load
- Actions (acknowledge, ...)

## What you can't do with it
- Use it without any knowledge of the API or at least the documentation for this package
 (but the documentation does not exist, so I doubt that someone is able to read it)
- ConfigurationManagement
 
## Usage examples for OOP interface

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
 