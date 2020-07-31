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

