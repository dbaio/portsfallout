#!/bin/sh

BASEDIR=$(dirname "$0")
cd "$BASEDIR" || exit 1

if [ "$1" = "today" ]; then
	DATESCRAPPER=$(/bin/date +%Y%m%d)
else
	# yesterday
	DATESCRAPPER=$(/bin/date -v-1d +%Y%m%d)
fi

CUR_TIME=$(/bin/date +%H-%m)

scrapy runspider \
	-o "scrapy_output/${DATESCRAPPER}_${CUR_TIME}.json" \
	-a "scrapydate=${DATESCRAPPER}" \
	--nolog \
	pkgfallout_scrapy_spider.py

python3 import-scrapy.py

mv scrapy_output/*.json scrapy_output/processed/

