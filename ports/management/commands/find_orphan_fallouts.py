# Copyright (c) 2020-2025 Danilo G. Baio <dbaio@FreeBSD.org>
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
import requests
from dateutil import parser
from django.core.management.base import BaseCommand
from django.utils import timezone as dtz
from ports.models import Port, Fallout
from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from scripts.pkgfallout_orphans_scrapy_spider import PkgfalloutOrphansScrapySpider
from twisted.internet import defer, reactor

class Command(BaseCommand):
    help = "Find orphan fallouts from the FreeBSD pkg-fallout archive"

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity')
        period = options.get("period", 30)
        period_date = dtz.make_aware(dtz.datetime.today() - dtz.timedelta(days=period))

        unique_urls = set()
        for f in Fallout.objects.filter(date__gte=period_date):
            base_url = "/".join(f.log_url.split("/")[:-1])
            if base_url not in unique_urls:
                unique_urls.add(base_url)

        @defer.inlineCallbacks
        def run_all_scrapers():
            for url in unique_urls:
                errors_url = url + "/errors/"
                if self.verbosity > 0:
                    self.stdout.write(f"Scraping: {errors_url}")

                log_urls = yield self.run_scraper(errors_url)
                for log_url in log_urls:
                    self.process_log_url(log_url)

            reactor.stop()

        reactor.callWhenRunning(run_all_scrapers)
        reactor.run()

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

        log_data = self.fetch_log_content(decoded_url)

        if not log_data:
            if self.verbosity > 0:
                self.stdout.write(f"  -> Skipping log due to failure: {decoded_url}")
            return

        extracted_details = self.extract_log_details(log_data, decoded_url)
        self.save_fallout_entry(extracted_details)

    def fetch_log_content(self, log_url):
        try:
            with requests.get(log_url, stream=True, timeout=10) as response:
                response.raise_for_status()

                log_lines = [line for line in response.iter_lines(decode_unicode=True)]

            return log_lines

        except requests.Timeout:
            self.stdout.write(f"   Request timed out: {log_url}")
            return None
        except requests.RequestException as e:
            self.stdout.write(f"   Error fetching log: {e}")
            return None

    def extract_log_details(self, log_data, log_url):
        """
        Extracts relevant details from log_data using regex and prepares an object for database insertion.
        """
        log_text = "\n".join(log_data)

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

        date_match = re.search(r"build of .*? \| .*? ended at (.+)", log_text)
        if date_match:
            extracted_data["date"] = date_match.group(1)

        maintainer_match = re.search(r"maintained by: (.+)", log_text)
        if maintainer_match:
            extracted_data["maintainer"] = maintainer_match.group(1)

        build_url_match = re.search(r"https://pkg-status.freebsd.org/(.+?)/data/(.+?)/(.+?)/logs/(.+?\.log)", log_url)
        if build_url_match:
            server, mastername, build_id, _ = build_url_match.groups()
            extracted_data["build_url"] = f"https://pkg-status.freebsd.org/{server}/build.html?mastername={mastername}&build={build_id}"

        flavor_match = re.search(r"FLAVOR=(.*)", log_text)
        if flavor_match:
            extracted_data["flavor"] = flavor_match.group(1).strip() or None

        port_name_match = re.search(r"=>> Building (.+)", log_text)
        if port_name_match:
            extracted_data["port_name"] = port_name_match.group(1)

        extracted_data["error_phase"] = self.find_failing_phase(log_data)

        package_match = re.search(r"package name: (.+)", log_text)
        if package_match:
            package_name = package_match.group(1).strip()
            extracted_data["version"] = package_name.split("-")[-1]

        env_match = re.search(r"MASTERNAME=(.+)", log_text)
        if env_match:
            extracted_data["env"] = env_match.group(1).strip()

        return extracted_data

    def find_failing_phase(self, log_data):
        """
        Reads the log from bottom to top and identifies the first 'phase' causing the failure.
        Example patterns:
        =======================<phase: lib-depends    >============================
        =======================<phase: configure      >============================
        """
        phase_pattern = re.compile(r"=======================<phase:\s*(\w+)\s*>============================")

        for line in reversed(log_data):
            match = phase_pattern.search(line)
            if match:
                return match.group(1)

        return None

    def save_fallout_entry(self, extracted_data):
        """
        Saves the extracted fallout data into the database.
        - If the entry exists, update it only if changes are detected.
        - If it doesn’t exist, create a new entry.
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

        try:
            if i_log_url.split('/')[2] == "pkg-status.freebsd.org":
                i_server = server_dict[i_log_url.split('/')[3]]
            else:
                i_server = i_log_url.split('/')[2]
        except:
            i_server = ""

        try:
            port = Port.objects.get(origin=i_port_name)
        except Port.DoesNotExist:
            port = None

        if port:
            fallout, created = Fallout.objects.get_or_create(
                port=port,
                env=i_env,
                version=i_version,
                category=i_category,
                maintainer=i_maintainer,
                last_committer=i_last_committer,
                date=i_date,
                log_url=i_log_url,
                build_url=i_build_url,
                report_url=i_report_url,
                defaults={'flavor': i_flavor,
                          'server': i_server}
            )

            if not created:
                changed_fields: int = 0
                if fallout.flavor != i_flavor:
                    fallout.flavor = i_flavor
                    changed_fields += 1

                if fallout.server != i_server:
                    fallout.server = i_server
                    changed_fields += 1

                if changed_fields > 0:
                    fallout.save()

        else:
            self.stdout.write(f"   Port not found: {i_port_name} – Entry not saved.")
