icinga2api_py
===============

Simple access to the Icinga2 API on top of Python [requests](https://github.com/psf/requests).

## What you can do with it
- Connect to an Icinga2 instance via API 
- Create objects
- Query objects: cached, with load on demand, auto-reload, ...
- Easy, object oriented access to all results
- Modify and delete objects, also multiple objects at once
- Actions (acknowledge, ...), also for multiple objects at once
- Receive easy-to-use objects from event streams
- Everything the Icinga2 API is capable of is somehow possible

## Usage examples

```python
from icinga2api_py import Icinga2

icinga = Icinga2("https://icinga:5665", auth=("username", "passwd"))

localhost = icinga.objects.hosts.localhost.get()

if not localhost["attrs.state"]:  # if state is not up
    print("The host 'localhost' seems to be down.")

# Iterate over service objects
for service in localhost.services:
    print(f"Service {service['name']} on {service.host['name']} has state {service['attrs.state']}")
```

## Notice, that ...
- ... knowledge of the Icinga2 API is recommended
- ... Python >=3.6 is required
- ... as soon as I think it's more stable, I will put it on PyPi (for easy pip installation);
 and it will get a version number >1.0 as soon as it's really stable. Both things haven't happen yet.

## How to install

Clone this repository and install via setup.py, for example like this:
 ```
 $ git clone https://github.com/TimL20/icinga2api_py.git
 $ cd icinga2api_py
 $ python setup.py install
 ```

Development takes place on different branches than the master branch.
