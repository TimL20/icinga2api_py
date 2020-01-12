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
Its one and only functionality is to return the class for an Icinga object.

In detail
- The `Types` class inherits from `CachedResultSet`
- It queries the Icinga API endpoint /types once, and caches the result forever
- It also caches already created classes forever
- The classes are dynamically created according to the information from the /types endpoint
- The following information is gathered and used from the /types endpoint
    - Name
    - Inheritance
    - Fields (attributes)
- Every class is a subclass of base.AbstractIcingaObject
- Singular and plural objects have different classes

But the information above is not true for all cases:
- The /types information is only quired on first use
- Not all classes are created as described in the /types information
    - The types Object, Objects, ConfigObject and ConfigObjects have custom hard-coded classes (module `objects`)
    - Other base classes (Number, String, Boolean, ...) also have custom classes to use the builtin Python types
- Dynamically created classes do not only have the fields specified for them, but also the fields of their parents

## base

The `base` module provides some basic classes, most important `AbstractIcingaObject`, which is the baseclass for every
class for mapped Icinga objects. The class provides some methods and properties:
- `__init__(*args, **kwargs)` method, which calls the super's init after popping "parent_descr" from kwargs or the last
    positional argument
- `parent_descr` attribute, see below
- `session` property to get the session the object belongs to
- classmethod `convert(obj, parent_descr)` to create the object from obj
- `type` property to get the singular type name
- `permissions(field)` to check permission for a given field

The "parent_descr" attribute is an object of `ParentObjectDescription`, to describe a parent of an object.
The "parent object" of an object A can be another "AbstractIcingaObject" B, in which case B has an field, whose
value is A.	In this case, parent and field have to be known.
In case an object has no parent (= is not a value for a field of another object), this description contains the
session the object belongs to.
The session attribute will reference to the session no matter which case is chosen. In case no session is given, the
session reference is copied from the parent object.

## simple_types

- Classes for describing Python builtin types (Number (int), String (str), Array (Sequence), ...)
- Also contains a `JSONResultEncoder` that is able to encode `AbstractIcingaObject` objects
- And a `JSONResultDecodeHelper` that provides a object_pairs_hook used on decoding JSON

The `NativeValue` subclasses emulate behavior of the builtin Python types while providing a consistant interface
- Timestamp should emulate both the builtin float and stdlib Datetime at once \[not fully implemented yet\]
- Array and Dictionary emulate the stdlib interfaces MutableSequence and MutableMapping respectivly
    - They know the "parent object" and what attribute they are in this "parent object"
    - Changes inside the sequence/mapping are propagated to the "parent object" \[not fully implemented yet\]
    - The parent object should send a modify request to Icinga
    - The sequence/mapping should not change if the request failed \[not fully implemented yet\]

## complex_types

This module contains 4 fundamendtal classes:
- `IcingaObjects` to map the Icinga type "Object" in its plural form
- `IcingaObject` to map the Icinga type "Object" in its singular form
- `IcingaConfigObjects` as a base class for any number of Icinga configuration object (maps "ConfigObject" plural form)
- `IcingaConfigObject` as a base class for exactly one Icinga configuration object (maps "ConfigObject" singular form)

The singular classes inherit from `results.SingleResultMixin` and their plural counterpart.

The most important class is `IcingaConfigObjects`, that provides:
- Automatically using the object_pairs_hook of the `JSONResultDecodeHelper` (see simple_types section)
- Returning a single `IcingaConfigObject` representing the object at a particular index
- Advanced attr specification parsing (in `parse_attrs()`), e.g. automatically prefixing "attrs" or "joins"
- Requesting modification for the Icinga configuration object(s), and using the new attributes if the request did not
  fail

The `IcingaConfigObject` class additionally provides or overrides:
- `__getitem__()` for getting the value for one field
- `__getattr__()` for getting the value for one field \[Does not really work as expected yet\]
