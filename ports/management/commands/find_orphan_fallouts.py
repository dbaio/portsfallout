# Copyright (c) 2020-2026 Danilo G. Baio <dbaio@FreeBSD.org>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import re
import urllib.parse
from datetime import timedelta

import requests
from dateutil import parser
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as dtz
from ports.models import Port, Fallout
from ports.utils import LOG_HEADER_FIELDS, ParseLogHeader
from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from scrapy.utils.reactor import install_reactor
from scripts.pkgfallout_orphans_scrapy_spider import PkgfalloutOrphansScrapySpider

# Scrapy refuses to crawl under a reactor other than the one it asks for, and
# importing `twisted.internet.reactor` installs the default one, so this comes
# first.
_scrapy_settings = get_project_settings()
if _scrapy_settings['TWISTED_REACTOR']:
    install_reactor(_scrapy_settings['TWISTED_REACTOR'],
                    _scrapy_settings['ASYNCIO_EVENT_LOOP'])

from twisted.internet import defer, reactor  # noqa: E402

USER_AGENT = 'portsfallout (+https://portsfallout.com)'

TIMEOUT = 30

# Only the two ends of a log are kept: the header, the environment dump and
# every phase marker are in the first kilobytes, the end time is the last line,
# and the compiler output in between reaches 174 MB.
LOG_HEAD_BYTES = 128 * 1024
LOG_TAIL_BYTES = 8 * 1024
LOG_CHUNK_BYTES = 64 * 1024

class Command(BaseCommand):
    help = "Find orphan fallouts from the FreeBSD pkg-fallout archive"

    def add_arguments(self, parser):

        parser.add_argument('period',
                            nargs='?',
                            type=int,
                            default=30,
                            help='Query entries from the last X days (default: 30)',)

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity')
        period = options.get("period") or 30
        period_date = dtz.now() - timedelta(days=period)

        unique_urls = set()
        for f in Fallout.objects.filter(date__gte=period_date):
            base_url = "/".join(f.log_url.split("/")[:-1])
            if base_url not in unique_urls:
                unique_urls.add(base_url)

        for log_url in self.scrape_log_urls(unique_urls):
            self.process_log_url(log_url)

    def scrape_log_urls(self, base_urls):
        """List the logs in the errors directory of every build

        All the crawling is done before a single result is read: the ORM
        refuses to be called from the reactor's async context.

        Arguments:
            base_urls [set] -- the build directories to look in
        Returns:
            [list] -- every log URL listed, across all of them
        """

        found = []
        failures = []

        # An error escaping the generator used to leave the reactor running
        # with nothing scheduled, and the command hung.
        @defer.inlineCallbacks
        def scrape_all():
            try:
                for url in base_urls:
                    errors_url = url + "/errors/"
                    if self.verbosity > 0:
                        self.stdout.write(f"Scraping: {errors_url}")

                    log_urls = yield self.run_scraper(errors_url)
                    found.extend(log_urls)
            except Exception as error:
                failures.append(error)
            finally:
                reactor.stop()

        reactor.callWhenRunning(scrape_all)
        reactor.run()

        if failures:
            raise CommandError(failures[0])

        return found

    def run_scraper(self, url):
        results = []

        class CustomSpider(PkgfalloutOrphansScrapySpider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.external_results = results

            def closed(self, reason):
                self.external_results.extend(self.log_urls)

        runner = CrawlerRunner(get_project_settings())

        @defer.inlineCallbacks
        def crawl():
            yield runner.crawl(CustomSpider, url=url)
            defer.returnValue(results)

        return crawl()

    def process_log_url(self, log_url):
        clean_url = log_url.replace("/errors", "", 1)
        decoded_url = urllib.parse.unquote(clean_url)

        if Fallout.objects.filter(log_url=decoded_url).exists():
            return
        else:
            if self.verbosity > 0:
                self.stdout.write(f"  -> Log NO exists in database: {decoded_url}")

        log = self.fetch_log_content(decoded_url)

        if log is None:
            if self.verbosity > 0:
                self.stdout.write(f"  -> Skipping log due to failure: {decoded_url}")
            return

        head, tail = log
        extracted_details = self.extract_log_details(head, tail, decoded_url)
        self.save_fallout_entry(extracted_details)

    def fetch_log_content(self, log_url):
        """Read the head and the tail of a build log, never the whole of it

        Arguments:
            log_url [string] -- the build log to read
        Returns:
            [tuple] -- the head and the tail as text, or None if the log could
                       not be read
        """

        head = bytearray()
        tail = bytearray()

        try:
            with requests.get(log_url, headers={'User-Agent': USER_AGENT},
                              stream=True, timeout=TIMEOUT) as response:
                response.raise_for_status()

                for chunk in response.iter_content(chunk_size=LOG_CHUNK_BYTES):
                    missing = LOG_HEAD_BYTES - len(head)
                    if missing > 0:
                        head += chunk[:missing]
                        chunk = chunk[missing:]

                    if chunk:
                        tail += chunk
                        del tail[:-LOG_TAIL_BYTES]

        except requests.Timeout:
            self.stdout.write(f"   Request timed out: {log_url}")
            return None
        except requests.RequestException as e:
            self.stdout.write(f"   Error fetching log: {e}")
            return None

        # Either end can be cut in the middle of a character.
        return head.decode("utf-8", "replace"), tail.decode("utf-8", "replace")

    def extract_log_details(self, head, tail, log_url):
        """
        Extracts relevant details from the two ends of a log using regex and prepares an object
        for database insertion.
        """
        # A log short enough to have been read whole carries its end time in
        # the head, having no tail of its own.
        ending = tail or head

        extracted_data = {
            "date": None,
            "maintainer": None,
            "log_url": log_url,
            "build_url": None,
            "flavor": None,
            "port_name": None,
            "report_url": None,
            "last_committer": None,
            "error_phase": None,
            "version": None,
            "env": None,
        }

        date_match = re.search(r"build of .*? \| .*? ended at (.+)", ending)
        if date_match:
            extracted_data["date"] = date_match.group(1)

        maintainer_match = re.search(r"maintained by: (.+)", head)
        if maintainer_match:
            extracted_data["maintainer"] = maintainer_match.group(1)

        build_url_match = re.search(r"https://pkg-status.freebsd.org/(.+?)/data/(.+?)/(.+?)/logs/(.+?\.log)", log_url)
        if build_url_match:
            server, mastername, build_id, _ = build_url_match.groups()
            extracted_data["build_url"] = f"https://pkg-status.freebsd.org/{server}/build.html?mastername={mastername}&build={build_id}"

        flavor_match = re.search(r"FLAVOR=(.*)", head)
        if flavor_match:
            extracted_data["flavor"] = flavor_match.group(1).strip() or None

        port_name_match = re.search(r"=>> Building (.+)", head)
        if port_name_match:
            extracted_data["port_name"] = port_name_match.group(1)

        extracted_data["error_phase"] = self.find_failing_phase(head)

        # The poudriere header carries the package name and the rest of the
        # build's provenance in one block.
        extracted_data.update(ParseLogHeader(head))

        if extracted_data["package_name"]:
            extracted_data["version"] = extracted_data["package_name"].split("-")[-1]

        env_match = re.search(r"MASTERNAME=(.+)", head)
        if env_match:
            extracted_data["env"] = env_match.group(1).strip()

        return extracted_data

    def find_failing_phase(self, head):
        r"""Identify the phase the build died in

        Poudriere writes a marker as it enters each phase, so the failing one
        is the last marker written.

        =======================<phase: lib-depends    >============================
        =======================<phase: configure      >============================

        The name is matched with a hyphen in it: `\w+` stops at one, and every
        dependency phase was read as the phase above it.

        Arguments:
            head [string] -- the head of a build log
        Returns:
            [string] -- the phase name, or None if the log has no marker
        """

        phases = re.findall(r"=+<phase:\s*([\w-]+)\s*>=+", head)

        return phases[-1] if phases else None

    def save_fallout_entry(self, extracted_data):
        """Store the fallout read out of a log

        `process_log_url` only gets here for a log the database does not
        hold. Should the crawler have stored it meanwhile, that row is the
        one with the report, and it is left as it is.
        """
        # From https://github.com/freebsd/pkg-status/blob/master/servers.txt
        server_dict = {
            'package18': 'package18.nyi.freebsd.org',
            'package19': 'package19.nyi.freebsd.org',
            'package20': 'package20.nyi.freebsd.org',
            'package21': 'package21.nyi.freebsd.org',
            'package22': 'package22.nyi.freebsd.org',
            'package23': 'package23.nyi.freebsd.org',
            'gohan01': 'gohan01.nyi.freebsd.org',
            'gohan02': 'gohan02.nyi.freebsd.org',
            'gohan03': 'gohan03.nyi.freebsd.org',
            'gohan04': 'gohan04.nyi.freebsd.org',
            'gohan05': 'gohan05.nyi.freebsd.org',
            'gohan06': 'gohan06.chi.freebsd.org',
            'beefy7': 'beefy7.nyi.freebsd.org',
            'beefy8': 'beefy8.nyi.freebsd.org',
            'beefy11': 'beefy11.nyi.freebsd.org',
            'beefy13': 'beefy13.nyi.freebsd.org',
            'beefy14': 'beefy14.nyi.freebsd.org',
            'beefy15': 'beefy15.nyi.freebsd.org',
            'beefy16': 'beefy16.nyi.freebsd.org',
            'beefy17': 'beefy17.nyi.freebsd.org',
            'beefy18': 'beefy18.nyi.freebsd.org',
            'beefy19': 'beefy19.nyi.freebsd.org',
            'ampere1': 'ampere1.nyi.freebsd.org',
            'ampere2': 'ampere2.nyi.freebsd.org',
            'ampere3': 'ampere3.nyi.freebsd.org',
            'ampere4': 'ampere4.chi.freebsd.org',
            'ampere5': 'ampere5.chi.freebsd.org',
            'beefy20': 'beefy20.chi.freebsd.org',
            'beefy21': 'beefy21.chi.freebsd.org',
            'beefy22': 'beefy22.chi.freebsd.org',
            'beefy23': 'beefy23.chi.freebsd.org',
            'beefy24': 'beefy24.chi.freebsd.org'
        }

        try:
            i_date = parser.parse(extracted_data["date"])
        except (TypeError, ValueError):
            self.stdout.write("   Invalid or missing date format.")
            return

        i_category = extracted_data["error_phase"] or ""
        i_env = extracted_data["env"] or ""
        i_version = extracted_data["version"] or ""
        i_maintainer = extracted_data["maintainer"] or ""
        i_last_committer = extracted_data["last_committer"] or ""
        i_log_url = extracted_data["log_url"]
        i_build_url = extracted_data["build_url"].replace('&amp;', '&') if extracted_data["build_url"] else ""
        i_report_url = extracted_data["report_url"] or ""
        i_flavor = extracted_data["flavor"] or ""
        i_port_name = extracted_data["port_name"] or ""
        i_log_details = {field: extracted_data.get(field) or ""
                         for field, _ in LOG_HEADER_FIELDS.values()}

        try:
            if i_log_url.split('/')[2] == "pkg-status.freebsd.org":
                i_server = server_dict[i_log_url.split('/')[3]]
            else:
                i_server = i_log_url.split('/')[2]
        except (IndexError, KeyError):
            i_server = ""

        try:
            port = Port.objects.get(origin=i_port_name)
        except Port.DoesNotExist:
            port = None

        if port:
            Fallout.objects.get_or_create(
                log_url=i_log_url,
                defaults={'port': port,
                          'env': i_env,
                          'version': i_version,
                          'category': i_category,
                          'maintainer': i_maintainer,
                          'last_committer': i_last_committer,
                          'date': i_date,
                          'build_url': i_build_url,
                          'report_url': i_report_url,
                          'flavor': i_flavor,
                          'server': i_server,
                          **i_log_details}
            )
        else:
            self.stdout.write(f"   Port not found: {i_port_name} – Entry not saved.")
