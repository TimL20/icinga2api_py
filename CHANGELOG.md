# New in v0.8.0

## IOM

- Objects for fields of other objects are now created on demand
  - The JSON encoder and decode helper were therefore no longer needed and removed
  - Accessing an item of an IOM object returns now the field object instead of the value
- Fixes for object modification
  - Fixed wrong handling of some value types
  - Fixed inconsistancy after modification (using icinga objects like nowhere else)
  - Fixed iom modification handling of sub-fields (incl. nested dictionaries)
- Improvements for object modification
  - Implemented partial modification (e.g. of only one field of a dictionary)
  - Implemented possibility for multiple modifications at once (for the same field)
- Moved iom IcingaConfigObjects __setattr__
  - This is a **backward icompatible change**
  - See commit 8850fdbe6a9357c41303234c2fbdfa23ba84b85d
- Improved simple_types.Dictionary
  - Implemented to handle strings only (because Icinga does that)
  - Accepting non-string keys (as Icinga also does)
  - Fixed returning container types


# New in v0.7.0

- A CHANGELOG.md, that acts like this is the first version ever, but should keep track of future changes
