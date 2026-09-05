Ports Fallout
=============

https://portsfallout.com/

- Django application
- Web crawling (Scrapy)

An easy way to search the FreeBSD pkg-fallout reports.

Be nice!


Running
-------

Install all requirements:

::

   $ pip install -r requirements.txt

On FreeBSD the same set is available from the ports tree:

::

   www/py-django52  www/py-djangorestframework  www/py-requests
   www/py-scrapy    devel/py-python-dateutil    dns/py-dnspython
   databases/py-mysqlclient


Copy the sample ``settings.py`` and configure your database access:

::

   $ cp portsfallout/settings_dev.py portsfallout/settings.py


Settings that must not be committed are read from the environment:

::

   PORTSFALLOUT_SECRET_KEY          required in production
   PORTSFALLOUT_DEBUG               "false" in production (default: true)
   PORTSFALLOUT_ALLOWED_HOSTS       comma separated list
   PORTSFALLOUT_CSRF_TRUSTED_ORIGINS  comma separated list, with the scheme
   PORTSFALLOUT_CACHE_DIR           defaults to ./cache, keep it off /tmp

Generate a secret key with:

::

   $ python -c 'from django.core.management.utils import get_random_secret_key; \
       print(get_random_secret_key())'

With ``PORTSFALLOUT_DEBUG=false`` the HTTPS related settings are enabled and
the debug toolbar is never loaded. Confirm a deployment with:

::

   $ python manage.py check --deploy


Create initial database:

::

   $ python manage.py migrate
   Operations to perform:
     Apply all migrations: admin, auth, contenttypes, ports, sessions
   Running migrations:
     Applying contenttypes.0001_initial... OK
     Applying auth.0001_initial... OK
     Applying admin.0001_initial... OK
     Applying admin.0002_logentry_remove_auto_add... OK
     Applying admin.0003_logentry_add_action_flag_choices... OK
     Applying contenttypes.0002_remove_content_type_name... OK
     Applying auth.0002_alter_permission_name_max_length... OK
     Applying auth.0003_alter_user_email_max_length... OK
     Applying auth.0004_alter_user_username_opts... OK
     Applying auth.0005_alter_user_last_login_null... OK
     Applying auth.0006_require_contenttypes_0002... OK
     Applying auth.0007_alter_validators_add_error_messages... OK
     Applying auth.0008_alter_user_username_max_length... OK
     Applying auth.0009_alter_user_last_name_max_length... OK
     Applying auth.0010_alter_group_name_max_length... OK
     Applying auth.0011_update_proxy_permissions... OK
     Applying ports.0001_initial... OK
     Applying sessions.0001_initial... OK


Populate database (ports and fallout info):

::

   $ ./scripts/cron-import-index.sh
   $ ./scripts/cron-scrapy.sh


Start web-server:

::

   $ python manage.py runserver


You can also fetch older fallouts:

::

   $ cd scripts

   Crawling messages from an specific month / Verbose
   $ scrapy runspider -O scrapy_output/2021-May.json \
      -a scrapydate="2021-May" pkgfallout_scrapy_spider.py

   Then import all .json files to database:
   $ python import-scrapy.py


More info in ``scripts/pkgfallout_scrapy_spider.py``.


The fallouts imported before the crawler started reading the poudriere header
of the build log have no package name, tree commits, poudriere version or
OSVERSIONs. One report is fetched from the archive per fallout, so the run is
bounded and can be repeated until it is done:

::

   $ python manage.py fill_log_details 30 --limit 500 -v 2



Cron jobs
---------

Execution for keeping the database always updated:

::

   # Update ports tree reference in the database
   30  0  *  *  *  /portsfallout/scripts/cron-import-index.sh

   # Fetch/import all pkg-fallout's reports from the Mlmmj archive of the
   # current month. Requests are cached, only new fallouts are fetched.
   45  0  *  *  *  /portsfallout/scripts/cron-scrapy.sh

   # Fetch/import pkg-fallout's from the last month
   30  10  *  *  *  /portsfallout/scripts/cron-scrapy.sh lastmonth

   # Update DNS values of the pkg-fallout servers
   45  3  *  *  *  python manage.py server_update
   45  3  *  *  *  python manage.py server_update -v 0  # no output


Tests
-----

::

   $ python manage.py test ports



API
---

A read-only REST API is served under ``/api/``, with no authentication:

::

   https://portsfallout.com/api/fallout/
   https://portsfallout.com/api/port/
   https://portsfallout.com/api/category/

A browser gets the browsable interface of Django REST framework, whose Filters
button carries the parameters below, and ``?format=json`` gets JSON. A single
object is at ``/api/<endpoint>/<id>/``.

Results are paginated with ``limit`` and ``offset``. The limit defaults to 50
and is capped at 500, so a full listing means following ``next`` until it is
null:

::

   $ curl -s 'https://portsfallout.com/api/fallout/?format=json&limit=2'

   {
     "count": 54231,
     "next": "https://portsfallout.com/api/fallout/?format=json&limit=2&offset=2",
     "previous": null,
     "results": [ { "url": ..., "port": { ... }, "env": ..., "maintainer": ... } ]
   }

Each fallout carries the port it belongs to, already expanded, so listing the
fallouts of a maintainer does not need a second request per row. The order is
fixed: fallouts newest first, ports by origin, categories by name.


Searching
~~~~~~~~~

Every endpoint takes a ``search`` parameter, matched case insensitively as a
substring against:

::

   /api/fallout/    maintainer, port origin, env, category
   /api/port/       origin, maintainer
   /api/category/   name

Several words are ANDed, and each one has to match one of the fields, not
necessarily the same one. A value containing spaces can be quoted to keep it
as a single term.

``search`` answers "it is one of these fields, I do not know which", so it is
the wrong tool once the field is known: ``search=ports`` also returns the
fallouts of ``ports-mgmt/*`` and of maintainers such as
``fbsd-ports@convectix.com``. Name the field instead.


Filtering
~~~~~~~~~

Each endpoint takes one parameter per field, named and matched exactly as in
the web interface, so the same value means the same thing in both places:

::

   /api/fallout/    maintainer    from the start of the address
                    port          substring of the origin
                    env           substring of the build environment
                    category      the build phase, exactly
                    flavor        substring of the flavor
                    date_after    on or after this moment
                    date_before   on or before this moment
   /api/port/       maintainer, port
   /api/category/   name          substring of the name

They combine, and every one of them takes a regular expression in place of a
plain value:

::

   $ curl -s 'https://portsfallout.com/api/fallout/?format=json&maintainer=ports'
   $ curl -s 'https://portsfallout.com/api/fallout/?format=json&maintainer=^(ports|x11)@&env=head-amd64'

A pattern that is too expensive to run, or that the database refuses, is a 400
naming the parameter rather than an error page:

::

   {"maintainer": ["Regular expression has nested quantifiers, which are too expensive to run."]}


Fallouts of a maintainer
~~~~~~~~~~~~~~~~~~~~~~~~

``maintainer`` matches from the start of the address, which covers both ways
of asking:

::

   Every address that begins with `ports`
   $ curl -s 'https://portsfallout.com/api/fallout/?format=json&maintainer=ports'

   That one address alone
   $ curl -s 'https://portsfallout.com/api/fallout/?format=json&maintainer=ports@FreeBSD.org'

The prefix does not reach ``fbsd-ports@convectix.com``, and filtering one
field leaves the ``ports-mgmt/*`` origins out as well. The same question put
to ``search`` returns all three.


Keeping a copy up to date
~~~~~~~~~~~~~~~~~~~~~~~~~

``date_after`` and ``date_before`` take a day or a full timestamp, and a value
without an offset is read as UTC:

::

   $ curl -s 'https://portsfallout.com/api/fallout/?format=json&date_after=2026-09-01'
   $ curl -s 'https://portsfallout.com/api/fallout/?format=json&date_after=2026-09-01T12:00:00Z'

Fallouts come back newest first, so a client that already holds a copy asks
for what is newer than the last date it saw and stops when ``next`` is null,
instead of walking the whole archive again.
