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


"""Filtering shared by the web interface and the API
"""

import logging
from datetime import datetime, time

from django.db import OperationalError
from django.db.models import Q
from django.template import loader
from django.utils import timezone as dtz
from django.utils.dateparse import parse_date, parse_datetime
from ports.utils import InvalidRegexError, IsRegex, ValidateRegex
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend
from rest_framework.settings import api_settings

logger = logging.getLogger(__name__)


def build_filter(field, value, fallback_lookup):
    """Build the Q object for one user supplied filter field

    A value that looks like a regex is validated before being handed to the
    database, anything else falls back to a plain lookup.

    Raises:
        InvalidRegexError -- if the value is a regex we refuse to run
    """

    if IsRegex(value):
        ValidateRegex(value)
        return Q(**{f'{field}__iregex': value})

    return Q(**{f'{field}__{fallback_lookup}': value})


def parse_moment(param, value):
    """Read one end of a date range

    A plain day is accepted as well as a timestamp, because a client walking
    the archive day by day has no time of day to give. A day is taken at
    midnight, and a value without an offset is read in the server timezone.

    Raises:
        ValidationError -- if the value is not a date at all
    """

    try:
        moment = parse_datetime(value)
        if moment is None:
            day = parse_date(value)
            moment = datetime.combine(day, time.min) if day else None
    except ValueError:
        # Well formed but not a real date, such as the 31st of February.
        moment = None

    if moment is None:
        raise ValidationError(
            {param: ['Expected a date (2026-09-01) or a timestamp (2026-09-01T12:00:00Z).']})

    return moment if dtz.is_aware(moment) else dtz.make_aware(moment)


class FieldFilterBackend(BaseFilterBackend):
    """One query parameter per field, named as in the web interface

    `search` answers "it is one of these fields, I do not know which", which is
    the wrong tool for "the fallouts of this maintainer": it matches a
    substring of any searched field, so `ports` also finds the ports-mgmt
    origins and the maintainers whose address merely ends in `ports@`.

    A view declares `filter_fields` as `{parameter: (field, lookup)}` for the
    text filters, and `date_filter_fields` for the two ends of a range.
    """

    template = 'ports/filters/fields.html'

    def filter_queryset(self, request, queryset, view):
        query = Q()

        for param, (field, lookup) in getattr(view, 'filter_fields', {}).items():
            value = request.query_params.get(param, '').strip()
            if not value:
                continue

            try:
                query.add(build_filter(field, value, lookup), Q.AND)
            except InvalidRegexError as error:
                raise ValidationError({param: [str(error)]})

        for param, (field, lookup) in getattr(view, 'date_filter_fields', {}).items():
            value = request.query_params.get(param, '').strip()
            if not value:
                continue

            query.add(Q(**{f'{field}__{lookup}': parse_moment(param, value)}), Q.AND)

        return queryset.filter(query)

    def to_html(self, request, queryset, view):
        """The filter form of the browsable API"""

        params = (list(getattr(view, 'filter_fields', {}))
                  + list(getattr(view, 'date_filter_fields', {})))
        if not params:
            return ''

        return loader.render_to_string(self.template, {
            'fields': [{'param': param, 'value': request.query_params.get(param, '')}
                       for param in params],
            # Filtering from the form would otherwise drop a search already in
            # the URL, since a form only submits its own inputs.
            'search_param': api_settings.SEARCH_PARAM,
            'search': request.query_params.get(api_settings.SEARCH_PARAM, ''),
        })

    def get_schema_operation_parameters(self, view):
        params = (list(getattr(view, 'filter_fields', {}))
                  + list(getattr(view, 'date_filter_fields', {})))
        return [{'name': param, 'required': False, 'in': 'query',
                 'schema': {'type': 'string'}} for param in params]


class FilterErrorMixin:
    """Turn a filter the database refuses into a 400 instead of a 500

    `ValidateRegex` rejects the patterns we know about, but the engine has its
    own dialect and the last word. A queryset is lazy, so its complaint does
    not arrive from the filter backend, it arrives later while the page is
    being counted or serialized, which is well past the point a backend could
    have caught it.
    """

    def handle_exception(self, exc):
        if isinstance(exc, OperationalError):
            logger.warning('Database rejected a user filter on %s',
                           self.request.get_full_path())
            exc = ValidationError(
                {'detail': ['The filter could not be evaluated by the database.']})

        return super().handle_exception(exc)
