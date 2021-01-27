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

import os
import sys
import requests
import bz2

sys.path.insert(1, r'../')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portsfallout.settings')

import django
django.setup()
from ports.models import Port


def fetch_index():
    url = "https://www.FreeBSD.org/ports/INDEX-13.bz2"
    r = requests.get(url, allow_redirects=True)
    open('INDEX-13.bz2', 'wb').write(r.content)


def populate_set():
    Ports = Port.objects.all().values('origin').order_by('origin')

    sPorts = set()
    for port in Ports:
        sPorts.add(port['origin'])

    return sPorts


def read_index(sPorts):
    with bz2.open('INDEX-13.bz2', mode='rt') as index_file:
        for row in index_file:
            row_list = row.split("|")
            p_origin = row_list[1].replace("/usr/ports/", "")

            if p_origin in sPorts:
                sPorts.remove(p_origin)

    return sPorts


def remove_orphans(sPortsOrp):
    for port in sPortsOrp:
        print('Removing {}'.format(port))
        Port.objects.filter(origin=port).delete()


if __name__ == "__main__":
    fetch_index()
    sPorts = populate_set()
    sPortsOrp = read_index(sPorts)
    remove_orphans(sPortsOrp)
