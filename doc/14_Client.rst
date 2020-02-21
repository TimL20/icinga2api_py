Client
======

The class ``Client`` is a subclass of ``API`` (usage described in “Basic
API Client”). This client uses a special query to create an object
containg the result(s) of a query (instead of the default
``APIResponse``). The class of the objects returned can be specified
with the results_class parameter of the ``Client`` constructor. By
default, the class is ``ResultsFromResponse``, but
``ResultsFromRequest`` and ``CachedResultSet`` are also supported.

No matter which of these classes used, with this client parsed responses
are returned. That why, this chapter gives some information about these
objects returned from each query with the client.

ResultSet
---------

An :class:`icinga2api_py.results.ResultSet` object represents a set of
results returned from the Icinga2 API.
This class is not an ABC (abstract base class), although it’s not meant
to be instanciated (rarely useful). ``ResultSet`` implements lot’s of
features for inspecting results from Icinga2:

- It’s a sequence. The “items” are ``Result`` objects (built on demand).
  You can get those ``Result``\ s by their index or iterate over them.
  It’s possible to get the results “naked” as a list via the ``results``
  property, however this is usually not really useful outside the library.
- It’s instead much more useful to slice a ``ResultSet``. Another
  ``ResultSet`` is returned.
- Every ``ResultSet`` has a ``load`` method and a ``loaded`` property,
  both useless with a general ``ResultSet``, but used in subclasses.
- Any fields (attrs) can be specified  with the dot-syntax
  e.g. "attrs.last_check_result.output" to get the output value of the
  last_check_result dictionary of the attrs dictionary.
- ``fields`` is a generator that yields all values of one attribute of
  all results in the ``ResultSet``. You can specify what to do if the
  attribute does not exist for an attribute (raise_nokey and
  nokey_value parameters).
- The ``where`` method returns all items (results), that have a expected
  value as an attribute. The expected value must have the same type. If a
  result does not have the attrite, the attribute value, the value is
  handled as if it’s a ``KeyError`` class (not an object, the class
  itself).
- The ``number`` methods counts, how many items (results) have an
  expected value for a particular attribute.
- The ``all`` method returns True, if all items (results) have an expected
  value for a particular attribute.
- The ``any`` method returns True, if minimum one item (result) has an
  expected value for a particular attribute.
- The ``min_max`` method returns True, if minuimum <min> and maximum <max>
  items (results) have an expected value.

These are the features of ``ResultSet``, which has many usefull
subclasses. Note that ``ResultSet`` and subclasses are not made to be
thread-safe.

ResultsFromResponse
~~~~~~~~~~~~~~~~~~~

``ResultsFromResponse`` is a ``ResultSet`` subclass to load (parse) the
results from a given ``APIResponse``. Objects of this class are returned
from the ``Client`` client.

ResultsFromRequest
~~~~~~~~~~~~~~~~~~

The ``ResultsFromRequest`` class implements to load the results of the
``ResultSet`` once (on demand) from a given request.

CachedResultSet
~~~~~~~~~~~~~~~

The class ``CachedResultSet`` inherits from ``ResultsFromRequest``. It
uses a request to load the response (and it’s results) on demand and
reload it after a cache_time. Objects of this class have some
specialized methods and properties:

- The ``cache_time`` property to get/set the cache time.
- The ``invalidate()`` method is there to reset the cache (to nothing).
  This way, the response is loaded for sure the next time it’s accessed.
- The ``fixed()`` method return a (generally) ResultSet of these results.
  This method was introduced if there might occur problems when reloading
  in the middle of usage in any other code.
- The methods ``hold`` and ``drop`` have a similar usecase. Call ``hold``
  to disable reload on cache expiry, and call ``drop`` to re-enable it.
  The same is done when using a ``CachedResultSet`` as a context manager.
  Note however, that calling ``hold`` does not assure that the results are
  not reloaded (e.g. it will reload after invalidate). Determining if
  calling ``drop`` is needed to re-enable the standard cache functionality
  can be done with the property ``held``.

ResultList
~~~~~~~~~~

The ``ResutList`` class extends the abilities of ``ResultSet`` (from
which it inherits) with being mutable like a standard Python list.

Result
------

Objects of the class ``Result`` are created e.g. dynamically (on demand)
from ``ResultSet`` and subclasses (by default) on accessing one item.
``Result`` objects are (immutable) Mappings. They accept the dot-syntax
for sub-attribute access

::

   value = res["attrs"]["last_check_result"]["output"]
   # Is the same as
   value = res["attrs.last_check_result.output"]

Objects of this classes behave like mappings *and* sequences.

- The length is always 0 or 1 (use ``len(result.keys())`` to get the
  number of keys) - sequence behavior
- Iterating will always just yield the object itself (exactly one time) -
  this is the sequence behavior
- When the mapping behavior is needed, use ``keys()`` explicitely

Examples
--------

::

   from icinga2api_py import Client
   # Create a client as with API
   client = Client.from_pieces("https://icinga:5665", auth=(user, passwd))

   # Get a ResultsFromResponse object
   appstatus = client.status.IcingaApplication.get()

   # Get something particular, int() as all JSON numbers are float by default
   pid = int(appstatus[0]["status"]["icingaapplication"]["app"]["pid"])
   print("Icinga runs with PID {}".format(pid))


   # Get one ResultsFromResponse containing every host that is down
   hosts = client.objects.hosts.filter("host.state==1").get()
   # Iterate over all those hosts
   for host in hosts:
       print(f"Host {host['name']} is down")


   # How much hosts are down
   print(f"Currently {len(hosts)} are down")

   # Print all host names (= get all "name" fields)
   print(", ".join(hosts.fields("name")))

   # Are they really all down? (= have all attrs.state attributes the value 1)
   if hosts.are_all("attrs.state", 1):
       print("They are really down!")

   # Is minimum one host down (= has min. one attrs.state attribute the value 1)
   if hosts.min_one("attrs.state", 1):
       print("At least one host is down")

   # List host names of hosts, that are in hard state
   down = hosts.where("attrs.state_type", 1).fields("name")
   print("The following host(s) are in hard state: " + ", ".join(down))


   # Output of last check result
   # Get value of attribute output in dictionary last_check_result in attrs
   localhost["attrs.last_check_result.output"]

These are just some examples. You may not want to use these things as
described above. But they are fine, and: they are also available when
using the layers above this layer (because of inheritance).
