# Icinga Object Mapping - "Behind the scenes"

This chapter aims to give an overview of how the IOM feature works internally, behind the "frontend" library API.

The chapter was written after I started reading my own code after not working at it for months. At least now, the code
is actually not well-written - it should be refactored later...

But at least the different parts of functionality are in different modules.

## session
The session module contains the classes `Session` (inherits from `API`) and `IOMQuery` (inherits from `Query`).

`Session` adds/overrides some attributes/methods
- client() returns a Client object
- api() returns an `API` object
- request_class is set to `IOMQuery`
- cache_time is the applied cache time, infinity by default
- types is a `Types` object of the `types` module

On calling a `IOMQuery` object (created on a query with a `Session` object), it returns
- An `APIResponse` object **if** the HTTP method is not GET
- The results as a `CachedResultSet` object, **if** the URL endpoint does not start with "/objects"
- Otherwise: A newly created object of an approriate class (got via the types attribute of the session)

## types

The `types` module is one of the most important modules for this feature.
Its one and only functionality is to return the class for a Icinga configuration object.

In detail
- The `Types` class inherits from `CachedResultSet`
- It queries the Icinga API endpoint /types once, and caches the result forever
- It also caches already created classes forever
- The classes are dynamically created according to the information from the /types endpoint
- The following information is gathered and used from the /types endpoint
    - Name
    - Inheritance
    - Fields (attributes)
- Singular and plural objects have different classes

But the information above is not true for all cases:
- The /types information is only quired on first use
- Not all classes are created as described in the /types information
    - The types Object, Objects, ConfigObject and ConfigObjects have custom hard-coded classes (module `objects`)
    - Other base classes (Number, String, Boolean, ...) also have custom classes to provide required functionality
- Dynamically created classes do not only have the fields specified for them, but also the fields of their parents

## attribute_value_types

- Contains types used as attribute values (Number, String, Boolean, ...)
- Also contains a `JSONResultEncoder` that is able to encode `AttributeValue` objects
- And a `JSONResultDecodeHelper` that provides a object_pairs_hook to use on decoding JSON

The `AttributeValue` subclasses emulate behavior of the builtin Python types while providing a consistant interface
- Timestamp should emulate both the builtin float and stdlib Datetime at once \[not fully implemented yet\]
- Array and Dictionary emulate the stdlib interfaces MutableSequence and MutableMapping respectivly
    - They know the "parent object" and what attribute they are in this "parent object"
    - Changes inside the sequence/mapping are propagated to the "parent object" \[not fully implemented yet\]
    - The parent object should send a modify request to Icinga
    - The sequence/mapping should not change if the request failed \[not fully implemented yet\]

## objects

This module contains 4 fundamendtal classes:
- `IcingaObjects` as a base class for any number of any Icinga object
- `IcingaObject` as a base class for exactly one of any Icinga object
- `IcingaConfigObjects` as a base class for any number of Icinga configuration object
- `IcingaConfigObject` as a base class for exactly one Icinga configuration object

The singular classes inherit from their plural counterpart and another singular class (e.g. `Result`).

The most important class is `IcingaConfigObjects`, that provides:
- Automatically using the object_pairs_hook of the `JSONResultDecodeHelper` (see above)
- A `session` property returning the `Session` object associated with this configuration object
- A `type` property returning the object's type name
- Returning a single `IcingaConfigObject` representing the object at a particular index
- Advanced attr specification parsing (in `parse_attrs()`), e.g. automatically prefixing attrs or joins
- Checking permission for a given field
- Requesting modification for the Icinga configuration object(s), and using the new attributes if the request did not
  fail

The `IcingaConfigObject` class additionally provides or overrides:
- `__getitem__()` for getting the value for one field
- `__getattr__()` for getting the value for one field \[Does not really work as expected yet\]
