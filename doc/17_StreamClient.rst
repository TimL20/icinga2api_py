StreamClient
============

The class ``StreamClient`` is a subclass of ``API`` (usage described in
“Basic API Client”). Making requests with this client works exactly the
same as with ``API`` or also the non-streaming ``Client``. The
StreamClient, as the name may suggest, adds the ability to easily
consume streamed content. For Icinga this is important for the Event
Streams, which allow to subscribe to an event type and receive events as
long as the socket is left open.

Look at this example to see how that works:

::

   with streamclient.events.types(["CheckResult"]).queue("abcdefg").post() as stream:
       i = 0
       for res in stream:
           print("Received check result: {}".format(res["check_result.output"]))
           i += 1
           if i > 4:
               break

In the first line a request is made, and the returned
``StreamClient.ResultStream`` is assigned to the variable stream. The
stream (connection) is closed as soon as close() is called; which is
also done when leaving the with block, so the with-statement is the
preffered way of doing this. The ``ResultStream`` is an iterable, that
returns a ``Result`` for each received line (event).

As the StreamClient just returns every line received as a ``Result``,
it will also work on non-streamed content, but the returned ``Result``
objects are very different from that of the non-streaming client.
