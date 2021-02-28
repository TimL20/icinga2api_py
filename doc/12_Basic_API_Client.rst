Basic API Client
================

There is a very basic API client in icinga2api_py.api named API, which
is a usefull wrapper around
`requests <https://github.com/requests/requests>`__. This client is
there to make building a request for the Icinga2 API easy. The client is
easy to customize by extending it in a subclass. By default,
the requests and responses built by this Client are
:class:`icinga2api_py.models.APIRequest`\ s and
:class:`icinga2api_py.models.APIResponse`\ s. The ``APIResponse`` object
is very similar to the Response object returned from a requests request
to the Icinga2 API (and that is not a coincidence).

The Client uses and inherits from requests.Session, this way data for
e.g. authentication is stored for all requests made with this client.

Construct an API client
-----------------------

Constructing an API client is easily done with a base URL and optionally some parameters.

::

   from icinga2api_py import API

   # Constructor
   apiclient = API(url, **sessionparams)

   # Example
   apiclient = API(
       "https://icingahost:5665",
       auth=("user", "pass"),
       verify="./icingahost.ca"
   )

-  The url is the Icinga2 API URL endpoint base.
   The client will try to append default scheme (https), port (5665) and
   API version (v1) if not specified, so the following URLs will do the
   same as the URL above: "icingahost", "icingahost:5665", ...
-  The sessionparams (keyword arguments) are key-value-pairs of
   attributes for the Session. Every requests.Session attribute is
   possible. It is important to use it for authentication.
   Authentication is passed here (both basic or certificates are
   supported). Other useful attributes are e.g. verify (Certificate
   verification) proxy (scheme->proxy mapping), trust_env (whether to
   trust environment variables for e.g. proxy).

Building a Request to a URL
---------------------------

Building a Icinga2 API request is usually really easy with this client.
Just look at these examples:

::

   client.status.IcingaApplication.get()
   client.objects.hosts.localhost.get()

   client.objects.services.s("localhost!test1").get()

These three are the simplest type of a request. What they do is to just
make, build (and fire) a request to a URL with a HTTP method. Let’s look
closer at this:

::

   <apiclient object> . status . IcingaApplication . get  ()

The five space and dot separated parts of this line say the following:

- Use this initialized API client (that’s obvious) that knows things as
  the base URL and authentication
- Add /status to the known base URL
- Add /IcingaApplication to the URL
- Override HTTP method with GET (X-HTTP-Method-Override is used)
- Fire the request (these are the brackets, as an ``APIRequest`` object
  sends the request whenever it’s called)

So that will just build the URL <baseurl>/status/IcingaApplication,
overrides the HTTP method with get and fires the request (using the API
session). If you like to look closer, leave out the brackets after the
HTTP method, that will give you a :class:`icinga2api_py.models.APIRequest`.
The APIRequest objects are callable, and will fire the requests on call.

As you can see, you usually just build a URL with converting the / in
the URL to a dot here. But there are sometimes cases, when you can’t do
that. For example, if you want to have the name of an object in the URL,
but this object has a special character in it’s name. That’s when you
want to use the special method ``s``. This method does exactly the same
as ``__getattr__`` would do usually (see the third request example
above).

You can also do it a bit more fancy like this:

::

   (client / "status" / "IcingaApplication").get()


Add something to the body
-------------------------

Adding something to the JSON body is done with calling an "attribute"
while building the request:

::

   <apiclient>.objects.hosts\
       .filter("host.name==\"localhost\"")\
       .attrs(["state"]).get()

   <apiclient>.objects.services\
       .filter("service.name==\"load\"")\
       .attrs("state", "state_type")\
       .joins(["host.state"]).get()

Just call a method between the URL building and the HTTP method. The
name of this method becomes the dictionary key in the body, the method
argument gets the value. If you give more than one argument, the value
automatically gets a list of all arguments. Adding multiple values is
also possible by repeating the key-and-value calls.
Omitting any values inside the "method" parenthesis will delete this key.

URL parameters
--------------

There are two possibilites for URL parameters (aka GET parameters).
First possibility: Add them as keyword arguments for the APIRequest
call:

::

   <apiclient>.objects.hosts.get(host="localhost")

Second possibility: Manipulate the request:

::

   req = <apiclient>.objects.hosts.get
   req.params.update({"host": "localhost"})
   req()

The second one is for the usecase, that firing the request is done
somewhere else than building it.

Response parsing
----------------

By default, any responses are :class:`icinga2api_py.models.APIResponse`
similiar to those returned directly returned from request. To change that
behavior, a subclass may override the ``create_response`` of the
``API`` class, which is called with the original ``requests.Response``.
