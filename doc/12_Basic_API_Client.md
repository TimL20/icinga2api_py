# Basic API Client
There is a very basic API client in icinga2api_py.api named API, which is a usefull wrapper around requests (that's the
only dependency). This client is there to make building a request for the Icinga2 API easy. By default, data is
returned as from requests, but we will see more about that later.
The Client uses and inherits from requests.Session.

## Construct an api.API client

```
from icinga2api_py import API
apiclient = API(host, auth=tuple(), port=5665, uri_prefix='/v1', response_parser=None, **sessionparams)
```

- host is the (Icinga2 API) host to connect to
- auth is the HTTP basic authentication tuple (username, password), use either this or cert_auth for authentication
- port is the TCP port to connect to
- uri_prefix is URL prefix, wich is currently (Icinga 2.9.1) always /v1
- response_parser is a callable to parse any response. That is discussed later. With None (default) no parser is used.
- Every other keyword arguments passed are set as requests.Session attributes, these are (among others):
  - proxies (Proxy dictionary)
  - verify (SSL Verification, False to disable verification)
  - cert (SSL client authentication, cert file or cert&key tuple)

## Building a Request (/Query) to a URL
Building a request for the API is usually really easy with this client. Just look at these examples:
```
client.status.IcingaApplication.get()
client.objects.hosts.localhost.get()

client.objects.services.s("localhost!test1").get()
```

These three are the simplest type of request. What they do is to just make, build (and fire) a request to a URL with a
HTTP method. Let's look closer at this:
```
<apiclient object>    .     status      .     IcingaApplication    .    get          ()
```
It just means:
- Use this initialized API client (that's obvious) and it's given base URL
- Add /status to the known base URL
- Add /IcingaApplication to the URL
- Override HTTP method with GET
- Fire the request

So that will just build the URL &lt;baseurl&gt;/status/IcingaApplication, sets the HTTP method to get and fires the
request via requests. If you like to look closer, leave out the brackets after the HTTP method, that will give you a
`icinga2api_py.API.Request` with the fields `request` (requests.Request) and  `headers` (headers to be set). The
API.Request objects are callable, and will fire the requests on call.

As you can see, you usually just build a URL with converting the / in the URL to a dot here. But there are sometimes
cases, when you can't do that. For example, if you want to have the name of an object in the URL, but this object has a
special character in it's name. That's when you want to use the special method `s`. This method does exactly the same
as `__getattr__` would do usually.

## Add something to the body
Adding something to the JSON body is very easy:
```
<apiclient>.objects.hosts.filter("host.name==\"localhost\"").attrs(["state"]).get()
<apiclient>.objects.services.filter("service.name==\"load\"").attrs("state", "state_type").joins(["host.state"]).get()
```

Just call a method between the URL building and the HTTP method. The name of this method becomes the dictionary key in
the body, the method argument gets the value. If you give more than one argument, the value automatically gets a list
of all arguments. Unlike with URL building, order is not important here.

## URL parameters
There is a possibility to add URL parameters (aka GET parameters):
```
<apiclient>.objects.hosts.get(host="localhost")
```

Just specify this as kwargs of the HTTP method call.

## Response parsing
By default, any reponses are returned as from requests. But you can specify a response_parser in the constructor of
API. This parser must be a callable object; it's called every time with the original requests response, and the result
of that is returned. That feature is used in the `icinga2api_py.Client`.