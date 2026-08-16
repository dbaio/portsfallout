Changelog
=========

Version 1.13.0
--------------

* Keep the poudriere log header of each fallout: the package name, the two
  ports tree commits, the poudriere version and both OSVERSIONs
* Regroup the fallout detail page, linking the commits to five ports tree
  mirrors and the OSVERSIONs to the porter's handbook
* Add the ``fill_log_details`` command, which reads the header of the fallouts
  imported before it

Version 1.12.0
--------------

* Address ports by their origin instead of their id, and redirect the old id
  URLs permanently
* Separate the fallout rows by day, following the timezone the date column is
  showing

Version 1.11.0
--------------

* Split the build environment name into its tree and its ports branch, and
  mark the quarterly branch with a rail
* Colour the build phase by family, so the fallouts that did not die in an
  ordinary build stand out from the ones that did
* Chip the build environments on the server list, and give the connectivity
  column a state dot instead of a strikethrough alone
* Lead the row actions with the log link

Version 1.10.1
--------------

* Stack the list tables into labelled blocks on narrow screens, instead of
  scrolling six columns sideways
* Stack the detail pages the same way
* Keep the theme toggle on the navbar's first line on a phone

Version 1.10.0
--------------

* Validate the user supplied regex filters before they reach the database,
  rejecting nested quantifiers and patterns the database cannot parse
* Report a rejected filter as a message instead of an error page
* Cap the ``limit`` accepted by the API
* Index the columns used by the filters and by the date ordering
* Avoid the N+1 queries on the fallout list and on the API
* Move the secret key, debug flag and allowed hosts to the environment
* Only load the debug toolbar when running with debug on
* Add the security settings reported by ``manage.py check --deploy``
* Move the file based cache out of ``/tmp``
* Require Django 5.2 LTS, 4.2 is end of life
* Add a test suite
* Use the ports 15 index

Version 1.9.3
-------------

* Add new servers, ampere4|ampere5

Version 1.9.2
-------------

* Add new servers, beefy23|beefy24

Version 1.9.1
-------------

* port-detail: Add support to display date/time in the local timezone

Version 1.9.0
-------------

* Add a new feature to track missing fallouts
* Add support to display date/time in the local timezone
* Use the ports 14 index

Version 1.8.2
-------------

* Open log links in a new window
* Fix the server import/match issue

Version 1.8.1
-------------

* navbar: Add missing option for the new maintainer page
* cmd/server_update: Process by default only the latest 60 days

Version 1.8.0
-------------

* Add a page to show an overview count by build environment and unique ports
* Add a page to show an overview count by maintainer and unique ports
* Track build environments per server

Version 1.7.3
-------------

* Dashboard: Show unique ports count
* scrapy: Fix duplicate entries issue

Version 1.7.2
-------------

* Improve paginator
* Display the object count on the list pages
* scrapy: Prepare to reprocess entries and fix server info
* Dashboard: Reword phrases

Version 1.7.1
-------------

* Remove whitespaces from single words searches
* scrapy: Get the correct server information

Version 1.7.0
-------------

* Remove deprecated parser module
* Remove deprecated Django ifnotequal
* Unpin Django<4
* Update third party plugins
* Dashboard: Use a bar graph for better visualization

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
