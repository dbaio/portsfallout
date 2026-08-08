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

"""Auxiliary functions for the application
"""

import re

# A user supplied regex is handed over to the database engine, which runs it
# against every row of the table. Keep the pattern short so a single request
# cannot turn into an expensive scan.
MAX_REGEX_LENGTH = 128

# Classic catastrophic backtracking signature: a quantifier applied to a group
# that already contains one, e.g. `(a+)+`, `(\w+\s?)*`, `(x{2,})+`.
NESTED_QUANTIFIER_RE = re.compile(r'\([^()]*[*+}][^()]*\)\s*[*+{]')

# Constructs that Python's `re` accepts but the MySQL/MariaDB regex engine
# rejects, where they surface as an uncaught OperationalError.
UNSUPPORTED_SYNTAX_RE = re.compile(r'\(\?(?:P[<=]|#|[aLu])')


class InvalidRegexError(ValueError):
    """A user supplied regex that we are not willing to run on the database."""


def IsRegex(raw_text):
    """Check if the string has characters used for regular expressions

    https://docs.python.org/3/library/re.html#regular-expression-syntax

    Ignoring dots because it's used in email addresses.

    Arguments:
        raw_text [string] -- *
    Returns:
        [bool] -- False if it's not matched
                  True if it matches
    """

    character_list = ['^', '$', '*', '+', '?', '{', '\\', '[', '(', '|', '!']

    if not any(str_char in character_list for str_char in raw_text):
        return False

    # Checked before compiling: an oversized pattern is not worth handing to
    # `re`, and `ValidateRegex` rejects it with a message anyway.
    if len(raw_text) > MAX_REGEX_LENGTH:
        return True

    try:
        re.compile(raw_text)
    except re.error:
        return False

    return True


def ValidateRegex(raw_text):
    """Reject user supplied regexes that are unsafe or unsupported

    `IsRegex` only tells us the string looks like a regex and compiles under
    Python. That is not enough: the pattern is evaluated by the database, whose
    engine has a different dialect and no protection against a pattern crafted
    to backtrack forever.

    Arguments:
        raw_text [string] -- pattern already accepted by `IsRegex`
    Raises:
        InvalidRegexError -- with a message suitable for display to the user
    """

    if len(raw_text) > MAX_REGEX_LENGTH:
        raise InvalidRegexError(
            f'Regular expression is too long (limit is {MAX_REGEX_LENGTH} characters).')

    if NESTED_QUANTIFIER_RE.search(raw_text):
        raise InvalidRegexError(
            'Regular expression has nested quantifiers, which are too expensive to run.')

    if UNSUPPORTED_SYNTAX_RE.search(raw_text):
        raise InvalidRegexError(
            'Regular expression uses syntax that the database does not support.')
