# Copyright (c) 2020 Danilo G. Baio <dbaio@bsd.com.br>
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

"""
Web crawling for freebsd-pkg-fallout mailman archive.
Be nice!

Execution:

  - Crawling messages from day -1 / Verbose
  $ scrapy runspider -o scrapy_output/2020-07-20.json pkgfallout_scrapy_spider.py

  - Crawling messages from an specific day / Verbose
  $ scrapy runspider -o scrapy_output/2020-07-10.json -a scrapydate=20200710 pkgfallout_scrapy_spider.py

  - Without logs
  $ scrapy runspider -o scrapy_output/2020-07-20.json --nolog pkgfallout_scrapy_spider.py

  - Crawling messages from an entirely month (Watch out!)
  $ scrapy runspider -o scrapy_output/2020-07.json -a scrapydate=202007 pkgfallout_scrapy_spider.py

"""

import scrapy
import re
from datetime import datetime, timedelta

class PkgfalloutScrapySpider(scrapy.Spider):
    name = "pkgfallout_scrapy"

    def start_requests(self):
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_raw = yesterday.strftime('%Y%m%d')

        url = 'https://lists.freebsd.org/pipermail/freebsd-pkg-fallout/'
        scrapydate = getattr(self, 'scrapydate', yesterday_raw)
        self.regex_pattern = '^' + scrapydate + '.*'
        yield scrapy.Request(url=url, callback=self.parse)


    def parse(self, response):
        # Mailman Archive Index
        for t_row in response.css('table tr td a'):
            if t_row.css('a::text').re(r'Thread'):
                link_pattern = t_row.css('a::attr(href)').get()
                if re.search(self.regex_pattern, link_pattern):
                    yield response.follow(link_pattern, callback=self.parse_issue_thread)


    def parse_issue_thread(self, response):
        # Mailman Date Thread
        for li in response.css('ul li a'):
            if li.css('a::text').re(r'\[package.*'):
                sublink = li.css('a::attr(href)').get()
                yield response.follow(sublink, callback=self.parse_issue)


    def parse_issue(self, response):
        # Mailman Issue Message
        if response.css('body b::text')[0].re(r'pkg-fallout'):
            yield {
                'description': response.css('title::text').get(),
                'date': response.css('body i::text').get(),
                'maintainer': response.css('body pre a::text')[0].get(),
                'last_committer': response.css('body pre a::text')[1].get(),
                'log_url': response.css('body pre a::text')[2].get(),
                'build_url': response.css('body pre a::text')[3].get(),
                'report_url': response.url,
            }

