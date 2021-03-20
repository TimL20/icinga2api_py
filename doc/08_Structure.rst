.. _doc-structure:

Structure
=========

This library consists of different “layers” and parts, that serve
different needs.

.. code:: text

                           +-------------------------+
                           |          IOM            |
                           | (Icinga object mapping) |
   +------------------+    |                         |
   |    Simple-OO     |    | subpackage iom          |
   | (Client: Icinga) |    | (Client: iom.Session)   |
   +------------------+----+-------------------------+
   |              Results-centered layer             |
   |                                                 |
   | (Clients: Client, StreamClient)                 |
   +-------------------------------------------------+
   |              Request-centered layer             |
   | (Client: API)                                   |
   +-------------------------------------------------+

The library has different layers. Each layer does only rely on modules
of the layer(s) below. Each layer aims to bring an advantage whenever
it’s used. Users of this library can use whatever layer they want to get
the benefits they need. The different layers have different clients to
use. In the following section, each layer should get a short
introduction.

Request-centered layer
----------------------

-  Used somehow by every part of this library, provides important basics
-  Is basically just a wrapper around the requests package
-  The benefit of this layer is to simplify sending requests to the
   Icinga API
-  This layer does almost nothing with the responses of the Icinga API
-  There are also some adjustments for performance and easier
   customization
-  The client of this layer is ``API``, every other client of this
   library inherits from this one
-  Documented in :ref:`doc-basic-api`

Result-centered layer
---------------------

-  Focuses on getting the results of the Icinga API responses
-  Also provides methods to easily work with the results, and optional
   features such as load-on-demand and caching
- Documented in :ref:`doc-client`

Simple-OO layer
---------------

-  “Object oriented” layer
- Focuses on working with Icinga configuration objects, e.g. provides
  methods to modify and delete such objects

IOM
---

-  “Icinga object mapping” aims to map every object in Icinga to an
   appropriate Python object
-  In development, not fully working yet
