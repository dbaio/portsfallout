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
import requests
import bz2

sys.path.insert(1, r'../')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portsfallout.settings')

import django
django.setup()
from ports.models import Category, Port


def fetch_index():
    url = "https://www.FreeBSD.org/ports/INDEX-13.bz2"
    r = requests.get(url, allow_redirects=True)
    open('INDEX-13.bz2', 'wb').write(r.content)


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

