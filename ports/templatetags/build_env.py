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

from django import template

register = template.Library()

BRANCHES = ('default', 'quarterly')


@register.filter(is_safe=True)
def env_split(env):
    """Split a build environment name into its tree and its ports branch

    ``144arm64-quarterly`` and ``main-amd64-default`` are two fields wearing one
    string: the tree being built, and the ports branch it was built from. The
    branch is the most repeated part of the column, so templates render it
    dimmed and use it to pick the rail style.

    The suffix keeps its leading dash, which lets a template concatenate the two
    halves back into the original name without knowing how it was cut. A name
    that does not end in a known branch comes back whole in ``head``, so an
    environment this does not recognise still renders as itself.
    """
    name = str(env or '').strip()
    head, sep, last = name.rpartition('-')

    if sep and last.lower() in BRANCHES:
        return {'head': head, 'branch': sep + last,
                'quarterly': last.lower() == 'quarterly'}

    return {'head': name, 'branch': '', 'quarterly': False}


@register.filter(is_safe=True)
def osversion(version):
    """Turn a ``__FreeBSD_version`` into the release it stands for

    The build log reports the host and the jail as ``1404000`` and ``1600019``,
    which is ``MMmmmPPP``: major, minor, and a patch level that says nothing a
    reader of this page is after. Anything that is not one of those numbers
    comes back untouched, so a value we cannot read still renders.
    """
    digits = str(version or '').strip()
    if not digits.isdigit():
        return digits

    number = int(digits)

    return f'{number // 100000}.{number % 100000 // 1000}'
