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

import re

from django import template

register = template.Library()

# The ports tree is published on several forges, and the same commit is
# reachable on all of them. cgit is the project's own and leads; the rest are
# there because a reader may already have an account on one, prefer its diff
# view, or sit behind a network where one of them does not load.
COMMIT_MIRRORS = (
    ('cgit', 'https://cgit.freebsd.org/ports/commit/?id={}'),
    ('GitHub', 'https://github.com/freebsd/freebsd-ports/commit/{}'),
    ('Codeberg', 'https://codeberg.org/freebsd/freebsd-ports/commit/{}'),
    # This one is the only one that insists on the capitalised organisation:
    # the lowercase path answers with a redirect.
    ('GitLab', 'https://gitlab.com/FreeBSD/freebsd-ports/-/commit/{}'),
    ('ron-dev', 'https://ron-dev.freebsd.org/FreeBSD/ports/commit/{}'),
)

# What the build log calls a commit. It is 40 characters today and was nine to
# eleven in the older logs, so the short forms have to pass too. Anything else
# is not something a forge can look up, and has no business in a URL.
COMMIT_RE = re.compile(r'^[0-9a-f]{7,40}$')


@register.filter(is_safe=True)
def commit_mirrors(commit):
    """List the ports tree forges that can show a commit

    Arguments:
        commit [string] -- a commit hash read from the build log
    Returns:
        [list] -- one ``{'name', 'url'}`` per mirror, empty for anything that
                  does not look like a hash
    """
    commit = str(commit or '').strip().lower()

    if not COMMIT_RE.match(commit):
        return []

    return [{'name': name, 'url': url.format(commit)}
            for name, url in COMMIT_MIRRORS]
