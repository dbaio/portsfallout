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

import time
from datetime import timedelta

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone as dtz
from scrapy import Selector

from ports.models import Fallout
from ports.utils import ParseLogHeader

USER_AGENT = 'portsfallout (+https://portsfallout.com)'

# Long enough that a slow archive page still lands, short enough that a stuck
# one does not hold the whole run.
TIMEOUT = 30


class Command(BaseCommand):
    help = ('Fill the poudriere log details of the fallouts imported before '
            'the crawler started reading them')

    def add_arguments(self, parser):

        parser.add_argument('period',
                            nargs='?',
                            type=int,
                            default=30,
                            help='Query entries from the last X days (default: 30)',)

        parser.add_argument('--limit',
                            type=int,
                            default=500,
                            help='Stop after fetching X reports (default: 500)',)

        parser.add_argument('--delay',
                            type=float,
                            default=0.5,
                            help='Seconds to wait between requests (default: 0.5)',)

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity')
        delay = options['delay']

        period_date = dtz.now() - timedelta(days=options['period'])

        # `package_name` is written for every log carrying the header block, so
        # a blank one is the mark of a fallout imported before this existed.
        # A report the archive cannot serve stays blank and is picked up again
        # on the next run, which is why the limit is there.
        pending = (Fallout.objects
                   .filter(date__gte=period_date, package_name='')
                   .exclude(report_url='')
                   .order_by('-date')[:options['limit']])

        filled = 0
        failed = 0

        for fallout in pending:
            if self.verbosity > 1:
                self.stdout.write(f'{fallout.report_url}')

            report = self.fetch(fallout.report_url)
            if report is None:
                failed += 1
                time.sleep(delay)
                continue

            details = ParseLogHeader(self.message_body(report))
            if not any(details.values()):
                if self.verbosity > 1:
                    self.stdout.write(self.style.WARNING('  no log header in the report'))
                failed += 1
                time.sleep(delay)
                continue

            for field, value in details.items():
                setattr(fallout, field, value)
            fallout.save(update_fields=list(details))
            filled += 1

            time.sleep(delay)

        if self.verbosity > 0:
            self.stdout.write(self.style.SUCCESS(f'Filled {filled} fallouts'))
            if failed:
                self.stdout.write(self.style.WARNING(f'{failed} reports could not be read'))

    def fetch(self, url):
        """Read a report page, reporting any failure as nothing to parse"""

        try:
            response = requests.get(url, headers={'User-Agent': USER_AGENT},
                                    timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as error:
            if self.verbosity > 0:
                self.stdout.write(self.style.ERROR(f'  {url}: {error}'))
            return None

    def message_body(self, report):
        """Pull the mail out of an archive page

        Mlmmj puts it in `pre.main`; the mailman pages kept from before May
        2021 use a bare `pre`, so both are tried. Going through a selector is
        what turns the escaped markup back into the log it was.
        """

        selector = Selector(text=report)
        body = ''.join(selector.css('pre.main ::text').getall())

        return body or ''.join(selector.css('pre ::text').getall())
