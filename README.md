icinga2api_py
===============

Simple access to the Icinga2 API on top of Python [requests](https://github.com/requests/requests).

## What you can do with it
- Connect to an Icinga2 instance via API 
- Create objects
- Query objects: cached, with load on demand and auto-reload
- Modify and delete objects, also multiple objects at once
- Actions (acknowledge, ...), also for multiple objects at once
- Everything except streams is somehow possible

## Notice, that ...
- ... knowledge of the Icinga2 API is recommended
- ... the documentation is not ready. Actually it's more a collection of working examples than a documentation...
- ... any streams (EventStreams) are currently not supported
- ... ConfigurationManagement is not available via object oriented interface
- ... A few things (Console feature, ConfigurationManagement and more) are not tested

## Usage examples for the object oriented interface

```
from icinga2api_py import Icinga2

icinga = Icinga2("icingahost", ("username", "passwd"))

localhost = icinga.objects.hosts.localhost.get()

if not localhost["attrs.state"]:  # if state is not up
    print("The host 'localhost' seems to be down.")

print("The host localhost has the following services:")
servicenames = [service["name"] for service in localhost.services]
print(", ".join(servicenames))
```

## How to install
 Clone this repository and install via setup.py, for example like this:
 ```
 $ git clone https://github.com/TimL20/icinga2api_py.git
 $ cd icinga2api_py
 $ python setup.py install
 ```

The branch dev tends to have more feature and better usability, but it is even more buggy than the master branch.
