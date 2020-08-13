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

   django
   django-bootstrap-pagination
   requests
   scrapy


Copy the sample ``settings.py`` and configure your database access:

::

   $ cp portsfallout/settings_dev.py portsfallout/settings.py


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
   $ ./scripts/cron-scrapy.sh today


Start web-server:

::

   $ python manage.py runserver


You can also fetch older fallouts:

::

   $ cd scripts

   Crawling messages from an specific day / Verbose
   $ scrapy runspider -o scrapy_output/2020-07-10.json \
      -a scrapydate=20200710 pkgfallout_scrapy_spider.py

   or

   Crawling messages from an entirely month (Watch out!)
   $ scrapy runspider -o scrapy_output/2020-07.json \
      -a scrapydate=202007 pkgfallout_scrapy_spider.py

   Then import all .json files to database:
   $ python import-scrapy.py


More info in ``scripts/pkgfallout_scrapy_spider.py``.



Cron jobs
---------

Execution for keeping the database always updated:

::

   # Update ports tree reference in the database
   30  0  *  *  *  /portsfallout/scripts/cron-import-index.sh

   # Fetch/import all pkg-fallout's reports from the Mailman archive
   # of the previous day
   45  0  *  *  *  /portsfallout/scripts/cron-scrapy.sh

   # Fetch/import pkg-fallout's of the current day (partials)
   30  10  *  *  *  /portsfallout/scripts/cron-scrapy.sh today
   30  18  *  *  *  /portsfallout/scripts/cron-scrapy.sh today

