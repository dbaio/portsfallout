import os
import sys
import requests
import bz2

sys.path.insert(1, r'../')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portsfallout.settings')

import django
django.setup()
from ports.models import Category, Port


def fetch_index():
    print("Fetching index...")
    url = "https://www.FreeBSD.org/ports/INDEX-13.bz2"
    r = requests.get(url, allow_redirects=True)
    open('INDEX-13.bz2', 'wb').write(r.content)
    print("Done")


def read_index():
    with bz2.open('INDEX-13.bz2', mode='rt') as index_file:
        for row in index_file:
            row_list = row.split("|")

            p_origin = row_list[1].replace("/usr/ports/", "")
            p_comment = row_list[3]
            p_maintainer = row_list[5]
            p_categories = row_list[6].split()
            p_www = row_list[9]

            try:
                port = Port.objects.get(origin=p_origin)
            except:
                port = None

            if port:
                different_fields = 0

                if port.main_category != p_origin.split("/")[0]:
                    port.main_category = p_origin.split("/")[0]
                    different_fields += 1

                if port.maintainer != p_maintainer:
                    port.maintainer = p_maintainer
                    different_fields += 1

                if port.comment != p_comment:
                    port.comment = p_comment
                    different_fields += 1

                if port.www != p_www:
                    port.www = p_www
                    different_fields += 1

                if different_fields > 0:
                    port.save()

            else:
                port = Port.objects.get_or_create(origin=p_origin,
                                            name=p_origin.split("/")[1],
                                            main_category=p_origin.split("/")[0],
                                            maintainer=p_maintainer,
                                            comment=p_comment,
                                            www=p_www)[0]

                # TODO: remove/update categories
                for category in p_categories:
                    category_obj = add_category(category)
                    port.categories.add(category_obj)


def add_category(name):
    category_name = name
    c = Category.objects.get_or_create(name=category_name)[0]
    #c.save()
    return c


if __name__ == "__main__":
    fetch_index()
    read_index()

