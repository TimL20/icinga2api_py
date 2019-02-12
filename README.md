icinga2api_py
===============

Simple access to the Icinga2 API on top of Python [requests](https://github.com/requests/requests).

## What you can do with it
- Connect to an Icinga2 instance via API 
- Create objects
- Query objects: cached, with load on demand, auto-reload, ...
- Modify and delete objects, also multiple objects at once
- Actions (acknowledge, ...), also for multiple objects at once
- Everything except streams is somehow possible

## Notice, that ...
- ... knowledge of the Icinga2 API is recommended
- ... any streams (EventStreams) are currently not supported

## Usage examples for the object oriented interface

```
from icinga2api_py import Icinga2

icinga = Icinga2("https://icingahost:5665/v1/", auth=("username", "passwd"))

localhost = icinga.objects.hosts.localhost.get()

if not localhost["attrs.state"]:  # if state is not up
    print("The host 'localhost' seems to be down.")

print("The host localhost has the following services:")
print(", ".join(localhost.services.values("name")))
```

## How to install

Clone this repository and install via setup.py, for example like this:
 ```
 $ git clone https://github.com/TimL20/icinga2api_py.git
 $ cd icinga2api_py
 $ python setup.py install
 ```

The branch dev tends to have more feature and better usability, but it is more buggy than the master branch.
