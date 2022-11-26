Changelog
=========

Unreleased
----------

* Remove deprecated parser module

Version 1.6.6
-------------

* Remove IPv4 proxy links to logs

Version 1.6.5
-------------

* Add IPv4 proxy links to logs

Version 1.6.4
-------------

* template: Combine common pagination code
* Update crawler following upstream changes

Version 1.6.3
-------------

* Update third party plugins
* Remove django-bootstrap-pagination, package is currently unmaintained

Version 1.6.2
-------------

* pkgfallout_scrapy_spider.py: Use full month name
* about: Fix freebsd-pkg-fallout URL


Version 1.6.1
-------------

* Django/Models: set implicitly Models AutoField
* cron-scrapy.sh: Remove scrapy json file
* cron-scrapy.sh: Use full month name


Version 1.6.0
-------------

* Model/Fallout: Increase version's size
* Add support to Mlmmj


Version 1.5.5
-------------

* Use humanize filter for numbers
* Add a message when no registry is found


Version 1.5.4
-------------

* Fix fallout history link in the port detail page
* Update Chart.js to v2.9.4
* Use table-responsive and don't wrap text
* Update Bootstrap to v4.5.3
* Fix FreshPorts name
* menu: Move burger icon to the right


Version 1.5.3
-------------

* Add flavors support


Version 1.5.2
-------------

* Add categories filter on Fallout list


Version 1.5.1
-------------

* Add management command ``clear_cache``: Clear whole cache


Version 1.5.0
-------------

* Add Server page for showing IPv4 and IPv6 connectivity
* Add management command ``server_update``:
  Update DNS values of the pkg-fallout servers
* Transform script remove_old_fallouts.py as a management command
* Add logo and favicon
* Update Bootstrap to v4.5.2


Version 1.4.0
-------------

* Add support for filtering with regular expressions


Version 1.3.0
-------------

* Add dashboard chart
* Add Chart.js v2.9.3


Version 1.2.0
-------------

* Add REST framework


Version 1.1.1
-------------

* Improve the fallouts query filter


Version 1.1.0
-------------

* Filter entries from the last 30 days in the dashboard
* Add running instructions
* Add fallout count column to the port list page
* Add fallout entry limits in the port detail page


Version 1.0.0
-------------

* Initial release
