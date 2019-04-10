# StreamClient
The class `icinga2api_py.StreamClient` is a subclass of `API` (usage described in "Basic API Client").
Making requests with this client works exactly the same as with `API` or also the non-streaming `Client`.
The StreamClient, as the name may suggest, adds the ability to easily consume streamed content.
For Icinga this is important for the Event Streams, which allow to subscribe to an event type and receive
events as long as the socket is left open.

Look at this example to see how that works:
```
with streamclient.events.types(["CheckResult"]).queue("abcdefg").post() as stream:
    i = 0
	for res in stream:
		print("Received check result: {}".format(res["check_result.output"]))
		i += 1
		if i > 4:
			break
```

In the first line a request is made, and the returned `icinga2api_py.StreamClient.ResponseStream` is
assigned to the variable stream. The stream (connection) is closed as soon as close() is called;
what is also done when leaving the with block, so the with-statement is the preffered way of doing this.
The `ResponseStream` is an iterable, that returns a `icinga2api_py.Result` for each received line (event).

The StreamClient just returns every line received as a `Result`, so it will also work on non-streamed content,
but the returned `Result` objects are propably different from that of the non-streaming client.
