# Copyright (c) 2020-2026 Danilo G. Baio <dbaio@FreeBSD.org>
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
import re
import sys
import requests
import bz2

sys.path.insert(1, r'../')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portsfallout.settings')

import django
django.setup()
from ports.models import Category, Port

INDEX_FILE = 'INDEX-15.bz2'
INDEX_URL = f'https://www.FreeBSD.org/ports/{INDEX_FILE}'


def fetch_index():
    with requests.get(INDEX_URL, allow_redirects=True, stream=True, timeout=60) as r:
        # Without this an error page would be written out as the index and only
        # fail later, during decompression.
        r.raise_for_status()
        with open(INDEX_FILE, 'wb') as index_file:
            for chunk in r.iter_content(chunk_size=65536):
                index_file.write(chunk)


# A `__FreeBSD_version` standing as a component of the version, which is how a
# kernel module carries the jail it was built for: `net/intel-em-kmod` is
# 7.7.8.1501503 in this INDEX and 7.7.8.1500033 out of a 15.0 jail. The two
# are the same port, so the number below says which jail built it, not which
# version the tree has, and comparing them would call every such build
# outdated. 111 ports of the INDEX carry one.
OSVERSION_RE = re.compile(r'(?:^|[.\-_])1[0-9]{6}(?:[._,]|$)')


def read_versions():
    """The version each port has in the tree, by origin

    A port with flavors has one row per flavor, and the version belongs to
    the port, so the rows agree. A handful carry one per flavor instead, as
    devel/libclc does for every LLVM release; those come back blank, since
    a fallout of one flavor held against the version of another would be
    called outdated for nothing, and not knowing is the honest answer.

    The same answer covers a version built around an OSVERSION, for the same
    reason: what the INDEX holds is one jail's build of it. Either way a blank
    only costs the ability to call that port's fallouts outdated, so a version
    this misreads as an OSVERSION is the cheap direction to be wrong in.
    """

    versions = {}

    with bz2.open(INDEX_FILE, mode='rt') as index_file:
        for row in index_file:
            pkgname, path = row.split("|", 2)[:2]

            origin = path.replace("/usr/ports/", "")
            # A version never holds a dash, so the last one ends the name.
            version = pkgname.rsplit("-", 1)[-1]

            if OSVERSION_RE.search(version):
                version = ""

            if versions.setdefault(origin, version) != version:
                versions[origin] = ""

    return versions


def read_index():
    versions = read_versions()

    with bz2.open(INDEX_FILE, mode='rt') as index_file:
        for row in index_file:
            row_list = row.split("|")

            p_origin = row_list[1].replace("/usr/ports/", "")
            p_comment = row_list[3]
            p_maintainer = row_list[5]
            p_categories = row_list[6].split()
            p_www = row_list[9]
            p_version = versions[p_origin]

            try:
                port = Port.objects.get(origin=p_origin)
            except Port.DoesNotExist:
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

                if port.version != p_version:
                    port.version = p_version
                    different_fields += 1

                if different_fields > 0:
                    port.save()

            else:
                port = Port.objects.get_or_create(origin=p_origin,
                                            name=p_origin.split("/")[1],
                                            main_category=p_origin.split("/")[0],
                                            maintainer=p_maintainer,
                                            comment=p_comment,
                                            www=p_www,
                                            version=p_version)[0]

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

