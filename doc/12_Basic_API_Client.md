# Basic API Client
There is a very basic API client in icinga2api_py.api named API, which is a usefull wrapper around requests (that's the
only dependency). This client is there to make building a request for the Icinga2 API easy. By default, data is
returned as from requests, but we will see more about that later.

## Construct an api.API client

```
from icinga2api_py import API
apiclient = API(host, auth=tuple(), cert_auth=tuple(), port=5665, uri_prefix='/v1', verify=False, response_parser=None)
```

- host is the host to connect to
- auth is the HTTP basic authentication tuple (username, password), use either this or cert_auth for authentication
- cert_auth is a tuple of a (client) certificate and key, use this for certificate authentication
- port is the TCP port to connect to
- uri_prefix is URL prefix, wich is currently (Icinga 2.9.1) always /v1
- verify is a path to a CA (/bundle) with truseted CA(s) (for self signed certificates)
 Set that to false (default) to disable verification, but that will cause warnings.
- response_parser is a callable to parse any response. That is discussed later. None (default) will not use a parser.

## Building a Request (/Query) to a URL
Building a request for the API is usually really easy with this client. Just look at these examples:
```
<apiclient>.status.IcingaApplication.get()
<apiclient>.objects.hosts.localhost.get()

<apiclient>.objects.services.s("localhost!test1").get()
```

These three are the simplest type of request. What they do is to just make build (and fire) a request to a URL with a
HTTP method. Let's look closer at this:
```
<apiclient>    .     status      .     IcingaApplication    .    get          ()
```
It just means:
- Use this API client (that's obvious) and it's given base URL
- Add /status to the known base URL
- Add /IcingaApplication URL
- Override HTTP method with GET
- Fire the request

So that will just build the URL &lt;baseurl&gt;/status/IcingaApplication, sets the HTTP method to get and fires the
request via requests. If you like to look closer, leave out the brackets after the HTTP method, that will give you a
`icinga2api_py.API.Request` with the fields `url` (used URL as string), `body` (JSON body), `method` (HTTP method
as string) and `request_args` (other request arguments) - objects of this class are sometimes used from the other
classes as a query. The API.Request objects are callable, and will fire the requests on call.

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
of all arguments. Unlike with URL building, order is not important here. And again, if you messed something up, leave
the brackets after the HTTP method away and look at the API.Request object.

## URL parameters
There is a possibility, to add URL parameters (aka GET parameters):
```
<apiclient>.objects.hosts.get(host="localhost")
```

Just specify this as kwargs of the HTTP method call.

## Response parsing
By default, any reponses are returned as from requests. But you can specify a response_parser in the constructor of
API. This parser must be a callable object; it's called every time with the original requests response, and the result
of that is returned. That feature is used in the `icinga2api_py.Client`.