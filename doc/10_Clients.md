# Clients
This library has different clients that have different capabilities.

## Basic API client
The base client is just called `API`. It is a wrapper around the requests package to make building a request and
parsing a response easy. The requests and responses built by this Client are `models.APIRequest`s and
`models.APIResponse`s.
Every other client inherits from `API`. `API` itself inherits from `requests.Session`. That way data like e.g.
authentication is stored.

## The Client client
This client is documented in "Client". `Client` inherits from `API`. The requests are here exactly the same as with
`API`, but after firing the request a ResultSet is returned, which provides a much better way of handling responses
with results from the Icinga2 API.

## The StreamClient client
This client is documented in "StreamClient". The `StreamClient` inherits from `API`, and building requests is exactly
the same as with `API`. On firing a request the `StreamClient` returns a `ResponseStream` object. This is an iterator,
yielding `Result` object for each responsed stream line from Icinga.

## Icinga2 OO Client
This client provides the feature of getting Icinga2 configuration objects represented as Python objects, with automatic
caching/load-on-demand
