Icinga Object Mapping
=====================

This library provides a feature called, which maps Icinga’s
configuration objects to Python objects. The self-invented name for this
feature is “Icinga Object Mapping”, or IOM for short. It aimes to be
comparable to Object Relational Mapping (ORM), as soon as it works
(which it doesn’t yet…). This chapter aims to give an introduction of
how to use this feature.

Session
-------

A ``Session`` object is a client that provides access to Icinga
configuration objects that are automatically mapped to Python objects.

Examples
~~~~~~~~~

::

   from icinga2api_py import Session
   session = Session("https://icinga:5665", auth=(user, password))

   host = session.objects.hosts.localhost.get()
   print(f"Host {host.name} has state {host.state}")


TODO: add more examples
