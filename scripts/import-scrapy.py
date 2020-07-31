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
    email_pieces = raw_email.split()
    user = email_pieces[0]
    domain = email_pieces[-1]
    return user + "@" + domain


def read_scrapy_json():
    path = 'scrapy_output/'
    json_list_files = [f for f in os.listdir(path) if f.endswith('.json')]
    #json_list_files = "20200710.json"

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
                i_server = row['log_url'].split('/')[2]
            except:
                i_server = ""

            try:
                port = Port.objects.get(origin=i_origin)
            except:
                port = None

            i_date = parser.parse(row['date'])

            if port:
                fallout = Fallout.objects.get_or_create(port=port,
                                                        env=i_env,
                                                        version=i_version,
                                                        category=i_category,
                                                        maintainer=process_mail(row['maintainer']),
                                                        last_committer=process_mail(row['last_committer']),
                                                        date=i_date,
                                                        log_url=row['log_url'],
                                                        build_url=row['build_url'],
                                                        report_url=row['report_url'],
                                                        server=i_server)[0]


if __name__ == "__main__":
    read_scrapy_json()
