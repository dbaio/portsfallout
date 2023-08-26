# Copyright (c) 2020-2023 Danilo G. Baio <dbaio@FreeBSD.org>
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

import os
import sys
import json
from dateutil import parser

sys.path.insert(1, r'../')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portsfallout.settings')

import django
django.setup()
from ports.models import Port, Fallout


def process_mail(raw_email):
    email_pieces = raw_email.split(' ')

    # mlmmj
    if len(email_pieces) == 1:
        return email_pieces[0]
    else:
        # mailman
        user = email_pieces[0]
        domain = email_pieces[-1]
        return user + "@" + domain


def read_scrapy_json():
    path = 'scrapy_output/'
    json_list_files = [f for f in os.listdir(path) if f.endswith('.json')]

    for json_file in json_list_files:
        with open(path + json_file, "r") as read_file:
            data = json.load(read_file)

        for row in data:
            row_list = row['description'].split()
            i_category = row_list[-1]

            raw_descr = row_list[2].replace("]", "").split("[")
            i_env = raw_descr[0]
            i_origin = raw_descr[1]

            i_version = row_list[5].split("-")[-1]
            if i_version[-1] == ",":
                i_version += row_list[6]

            try:
                if row['log_url'].split('/')[2] == "pkg-status.freebsd.org":
                    i_server = row['log_url'].split('/')[3] + '.nyi.freebsd.org'
                else:
                    i_server = row['log_url'].split('/')[2]
            except:
                i_server = ""

            try:
                port = Port.objects.get(origin=i_origin)
            except:
                port = None

            i_date = parser.parse(row['date'])

            if port:
                fallout, created = Fallout.objects.get_or_create(port=port,
                                                        env=i_env,
                                                        version=i_version,
                                                        category=i_category,
                                                        maintainer=process_mail(row['maintainer']),
                                                        last_committer=process_mail(row['last_committer']),
                                                        date=i_date,
                                                        log_url=row['log_url'],
                                                        build_url=row['build_url'].replace('&amp;','&'),
                                                        report_url=row['report_url'],
                                                        defaults={'flavor': row['flavor'],
                                                                  'server': i_server}
                                                        ,)

                if not created:
                    changed_fields: int = 0
                    if fallout.flavor != row['flavor']:
                        fallout.flavor = row['flavor']
                        changed_fields += 1

                    if fallout.server != i_server:
                        fallout.server = i_server
                        changed_fields += 1

                    if changed_fields > 0:
                        fallout.save()


if __name__ == "__main__":
    read_scrapy_json()
