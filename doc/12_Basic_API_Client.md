# Basic API Client
There is a very basic API client in icinga2api_py.api named API, which is a usefull wrapper around
[requests](https://github.com/requests/requests). This client is there to make building a request for the Icinga2 API
easy. By default, the requests and responses built by this Client are `models.APIRequest`s and
`models.APIResponse`s. The APIResponse object is the really similar to the Response object returned from a requests
request to the Icinga2 API (and that is not a coincidence).
The Client uses and inherits from requests.Session, this way data like e.g. authentication data is stored for all
requests done with this client.

## Construct an API client

There are two ways to construct the API client.
```
from icinga2api_py import API

# Constructor
apiclient = API(url, **sessionparams)

# Alternative constructor
apiclient = API.from_pieces(host, port, url_prefix, **sessionparams)

# Examples
apiclient = API("https://icingahost:5665/v1/", auth=("user", "pass"), verify="./icingahost.ca")
# Is the same as
apiclient = API.from_pieces("icingahost", auth=("user", "pass"), verify="./icingahost.ca")
```

- The url is the Icinga2 API URL endpoint base including the versioning. Example:
 https://localhost:5665/v1/
- With the alternative constructor the URL is built from host, port and url_prefix.
 This is usefull, as port and url_prefix have default values (5665 and "/v1") here.
- The sessionparams (keyword arguments) are key-value-pairs of attributes for the Session. Every requests.Session
 attribute is possible. It is important to use it for authentication. Authentication is  passed here (both basic or
 certificates are supported).

## Building a Request to a URL

Building a Icinga2 API request is usually really easy with this client. Just look at these examples:
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
- Use this initialized API client (that's obvious) which knows things as the base URL and authentication
- Add /status to the known base URL
- Add /IcingaApplication to the URL
- Override HTTP method with GET (X-HTTP-Method-Override is used)
- Fire the request (these are the brackets, as a APIRequest fires when it's called)

So that will just build the URL &lt;baseurl&gt;/status/IcingaApplication, overrides the HTTP method with get and fires
the request (on the API session). If you like to look closer, leave out the brackets after the HTTP method, that will
give you a `icinga2api_py.models.APIRequest`. The APIRequest objects are callable, and will fire the requests on
call.

As you can see, you usually just build a URL with converting the / in the URL to a dot here. But there are sometimes
cases, when you can't do that. For example, if you want to have the name of an object in the URL, but this object has a
special character in it's name. That's when you want to use the special method `s`. This method does exactly the same
as `__getattr__` would do usually (see the third request example above).

## Add something to the body

Adding something to the JSON body is very easy:
```
<apiclient>.objects.hosts.filter("host.name==\"localhost\"").attrs(["state"]).get()
<apiclient>.objects.services.filter("service.name==\"load\"").attrs("state", "state_type").joins(["host.state"]).get()
```

Just call a method between the URL building and the HTTP method. The name of this method becomes the dictionary key in
the body, the method argument gets the value. If you give more than one argument, the value automatically gets a list
of all arguments. Unlike URL building, order is not important here.

## URL parameters

There are two possibilites for URL parameters (aka GET parameters).
First possibility: Add them as keyword arguments for the APIRequest call:
```
<apiclient>.objects.hosts.get(host="localhost")
```

Second possibility: Manipulate the request:
```
req = <apiclient>.objects.hosts.get
req.params.update({"host": "localhost"})
req()
```
The second one is for the usecase, that firing the request is done somewhere else as building it.

## Response parsing

By default, any responses are `models.APIResponse` similiar to those returned directly returned from request.
To change that behavior, you could create a subclass overriding the `create_response` of the `API` class, which is
called with the original requests response.
