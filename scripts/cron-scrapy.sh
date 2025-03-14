#!/bin/sh
#
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

export LANG=en_US.UTF-8

BASEDIR=$(dirname "$0")
cd "$BASEDIR" || exit 1

if [ "$1" = "lastmonth" ]; then
	DATESCRAPPER=$(/bin/date -v-1m +%Y-%B)
else
	DATESCRAPPER=$(/bin/date +%Y-%B)
fi

scrapy runspider \
	-O "scrapy_output/${DATESCRAPPER}.json" \
	-a "scrapydate=${DATESCRAPPER}" \
	--nolog \
	pkgfallout_scrapy_spider.py

python3 import-scrapy.py

# keep for history
if [ "$1" = "lastmonth" ]; then
	mv "scrapy_output/${DATESCRAPPER}.json" scrapy_output/processed/
else
	rm -f "scrapy_output/${DATESCRAPPER}.json"
fi
