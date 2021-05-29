# Copyright (c) 2020-2021 Danilo G. Baio <dbaio@bsd.com.br>
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
Web crawling for freebsd-pkg-fallout mlmmj archive.
Be nice!

Execution:

  - Crawling messages from current month / Verbose
  $ scrapy runspider -o scrapy_output/current_month.json pkgfallout_scrapy_spider.py

  - Crawling messages from specific month / Verbose
  $ scrapy runspider -o scrapy_output/2021-May.json scrapydate="2021-May" pkgfallout_scrapy_spider.py

  - Crawling messages from current month / Without logs
  $ scrapy runspider -o scrapy_output/current_month.json --nolog pkgfallout_scrapy_spider.py

"""

import scrapy
import re
from datetime import datetime, timedelta
from scrapy.utils.httpobj import urlparse_cached

# https://github.com/scrapy/scrapy/blob/master/scrapy/extensions/httpcache.py#L23
class CustomPolicyPkgFallout(object):

    def __init__(self, settings):
        self.ignore_schemes = settings.getlist('HTTPCACHE_IGNORE_SCHEMES')
        self.ignore_http_codes = [int(x) for x in settings.getlist('HTTPCACHE_IGNORE_HTTP_CODES')]

    def should_cache_request(self, request):
        if request.url.split("/")[-1] == 'index.html':
            # Do not cache index.html
            return False
        return urlparse_cached(request).scheme not in self.ignore_schemes

    def should_cache_response(self, response, request):
        return response.status not in self.ignore_http_codes

    def is_cached_response_fresh(self, cachedresponse, request):
        return True

    def is_cached_response_valid(self, cachedresponse, response, request):
        return True


class PkgfalloutScrapySpider(scrapy.Spider):
    name = "pkgfallout_scrapy"

    custom_settings = {
        'HTTPCACHE_ENABLED': True,
        'HTTPCACHE_GZIP': True,
        'HTTPCACHE_POLICY': CustomPolicyPkgFallout,
    }

    def start_requests(self):
        cur_month_raw = datetime.now()
        cur_month = cur_month_raw.strftime('%Y-%b')

        scrapydate = getattr(self, 'scrapydate', cur_month)
        url = 'https://lists.freebsd.org/archives/freebsd-pkg-fallout/' + scrapydate + '/index.html'

        self.regex_pattern = '^[0-9]+.html'
        yield scrapy.Request(url=url, callback=self.parse)


    def parse(self, response):
        # Mlmmj Archive Index
        for t_row in response.css('ul li'):
            if t_row.css('a::attr(href)').re(r'^[0-9]+.html'):
                link_pattern = t_row.css('a::attr(href)').get()
                if re.search(self.regex_pattern, link_pattern):
                    yield response.follow(link_pattern, callback=self.parse_mail)


    def parse_mail(self, response):
        # Mlmmj Message
        if (response.xpath("//meta[@name='Author']/@content")[0].re(r'^pkg-fallout') and
                response.xpath("//meta[@name='Subject']/@content")[0].re(r'^\[package')):
            yield {
                'description': response.css('body div.head h1::text').get(),
                'date': response.css('body div.mail span#date::text').get().split(': ')[-1],
                'maintainer': response.css('body div.mail pre').re_first(r'Maintainer:\s*(.*)').replace('_at_','@'),
                'last_committer': '',
                'log_url': response.css('body div.mail pre').re_first(r'Log URL:\s*(.*)'),
                'build_url': response.css('body div.mail pre').re_first(r'Build URL:\s*(.*)'),
                'flavor': response.css('body pre::text').re_first(r'FLAVOR=.*').split('=')[-1],
                'report_url': response.url,
            }
