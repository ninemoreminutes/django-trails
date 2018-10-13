Django Trails
=============

Django Trails is a Django app to provide audit logging capability for a Django
project.  Its main goals are to:

* Capture database changes using signals.
* Log user and changes to the database.
* Log user and changes using Python logging library.
* Provide admin interface to view full audit trail for an object or user.
* Provide flexible template-based rendering of audit trails.

While a number of parts are functional, it is still considered alpha quality
and does not yet support the following:

* Capturing changes made to many to many relationships.
* Tests to verify correct handling of proxy models or model inheritance.
* Tests to verify handling of custom model fields.
* Actually using the Python logging module.
