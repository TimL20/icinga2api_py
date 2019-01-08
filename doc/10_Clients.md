# Clients
This library is structured in three layers:

| Layer number | Client | Inherits from | Short description |
|:------------ |:------ |:------------- |:----------------- |
| 1 | API | - | Base client - basically just a simple wrapper to make requests to Icinga2 easier |
| 2 | Client | API | Parses responses from Icinga2 for easier (results) access |
| 3 | Icinga2 | Client | Object oriented access |

## Basic API client
This client is everything of the module icinga2api_py.api. This module could be used standalone.
It is documented in "Basic_API_Client".

## Proper Client
This Client is documented in "Client".

## Icinga2 OO Client
This client is documented in "OO".
