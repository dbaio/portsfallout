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

# The poudriere phase a build died in, grouped into the four answers a
# maintainer is actually after. `build` is the family that means the port
# itself broke, and is the one the stylesheet gives the accent to.
PHASE_FAMILIES = {
    'patch': 'build',
    'configure': 'build',
    'build': 'build',

    'pkg-depends': 'dep',
    'fetch-depends': 'dep',
    'extract-depends': 'dep',
    'patch-depends': 'dep',
    'build-depends': 'dep',
    'lib-depends': 'dep',
    'run-depends': 'dep',

    'fetch': 'src',
    'checksum': 'src',
    'extract': 'src',

    'check-sanity': 'pkg',
    'stage': 'pkg',
    'package': 'pkg',
    'install': 'pkg',
    'install-mtree': 'pkg',
    'deinstall': 'pkg',
}


@register.filter(is_safe=True)
def phase_family(category):
    """Map a build phase to the family the stylesheet colours it by

    A phase can arrive carrying the reason it ended, as `build/runaway` or
    `package/timeout`. That tail says how the build died, not where, so the
    family comes from the phase in front of it: a runaway build is still a
    build failure and belongs in the same group as a plain one.

    The phase is whatever the log reported, so anything still unrecognised
    falls back to a neutral family rather than losing its styling. Adding a
    phase poudriere grows later is a one line change to the table above.
    """
    phase = str(category or '').strip().lower().partition('/')[0]

    return PHASE_FAMILIES.get(phase, 'none')
