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

import logging
from datetime import timedelta

from django.http import Http404
from django.shortcuts import render
from django.views.generic import View, TemplateView, ListView, DetailView
from django.db import OperationalError
from django.db.models import Count, Q
from django.db.models.functions import TruncDay
from ports.models import Port, Category, Fallout, Server
from ports.pagination import CappedLimitOffsetPagination
from ports.serializers import CategorySerializer, PortSerializer, FalloutSerializer
from ports.utils import InvalidRegexError, IsRegex, ValidateRegex
from rest_framework import filters, viewsets
from django.utils import timezone as dtz

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


class RegexFilterMixin:
    """Turn a rejected filter into a message instead of an error page

    A filter can fail in two ways: `ValidateRegex` refuses it up front, or the
    database engine rejects it once the query runs. Both end up as an empty
    result list plus `filter_error` in the context.
    """

    filter_error = None

    def paginate_queryset(self, queryset, page_size):
        """Fall back to the last page instead of raising a 404

        Narrowing a filter while on page 5 leaves a stale `page` in the URL, and
        so do bookmarks and the back button. Retrying only on the error keeps
        the extra count out of the common path.
        """

        try:
            return super().paginate_queryset(queryset, page_size)
        except Http404:
            # A number past the end is a stale page, so the last one is what
            # was meant. Anything else is nonsense and starts over at the first.
            try:
                past_the_end = int(self.request.GET.get(self.page_kwarg)) > 1
            except (TypeError, ValueError):
                past_the_end = False

            self.kwargs[self.page_kwarg] = 'last' if past_the_end else 1
            return super().paginate_queryset(queryset, page_size)

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except OperationalError:
            logger.warning('Database rejected a user filter on %s', request.get_full_path())
            self.filter_error = 'The filter could not be evaluated by the database.'
            self.object_list = self.model.objects.none()
            return self.render_to_response(
                self.get_context_data(object_list=self.object_list))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_error'] = self.filter_error
        return context


def dashboard(request):
    context = {}

    from_date = dtz.now() - timedelta(days=30)

    fallout_cat = Fallout.objects.filter(date__gte=from_date).values('category').annotate(total=Count('category'), total_ports=Count('port', distinct=True)).order_by('-total')[:20]
    context['fallout_cat'] = fallout_cat

    fallout_env = Fallout.objects.filter(date__gte=from_date).values('env').annotate(total=Count('env'), total_ports=Count('port', distinct=True)).order_by('-total')[:20]
    context['fallout_env'] = fallout_env

    fallout_main = Fallout.objects.filter(date__gte=from_date).values('maintainer').annotate(total=Count('maintainer'), total_ports=Count('port', distinct=True)).order_by('-total')[:20]
    context['fallout_main'] = fallout_main

    fallout_flavor = Fallout.objects.filter(date__gte=from_date).values('flavor').exclude(flavor__exact='').annotate(total=Count('flavor'), total_ports=Count('port', distinct=True)).order_by('-total')[:20]
    context['fallout_flavor'] = fallout_flavor

    fallout_count_recent = Fallout.objects.filter(date__gte=from_date).count()
    context['fallout_count_recent'] = fallout_count_recent

    context['fallout_ports_recent'] = (Fallout.objects.filter(date__gte=from_date)
                                       .values('port').distinct().count())

    fallout_count = Fallout.objects.count()
    context['fallout_count'] = fallout_count

    fallout_recent = Fallout.objects.all().values().order_by('-date').first()
    context['fallout_recent'] = fallout_recent

    fallout_oldest = Fallout.objects.all().values().order_by('date').first()
    context['fallout_oldest'] = fallout_oldest

    # Chart: daily totals split by the three build environments reporting the
    # most fallouts, with everything else folded into a fourth bucket. A flat
    # daily total does not say why a day is big; this does.
    top_envs = [row['env'] for row in
                Fallout.objects.filter(date__gte=from_date).values('env')
                .annotate(total=Count('id')).order_by('-total')[:3]]
    series = top_envs + ['others']

    daily = (Fallout.objects.filter(date__gte=from_date)
             .annotate(day=TruncDay('date')).values('day', 'env')
             .annotate(total=Count('id')).order_by('day'))

    per_day = {}
    for row in daily:
        day = row['day'].date()
        bucket = row['env'] if row['env'] in top_envs else 'others'
        per_day.setdefault(day, dict.fromkeys(series, 0))
        per_day[day][bucket] += row['total']

    peak = max((sum(counts.values()) for counts in per_day.values()), default=0)

    chart = []
    for day in sorted(per_day):
        counts = per_day[day]
        total = sum(counts.values())
        chart.append({
            'day': day,
            'total': total,
            # Percentage of the plot height; the segments are then a
            # percentage of the bar, so both resolve in CSS.
            'height': total * 100.0 / peak if peak else 0,
            'segments': [{'name': name, 'count': counts[name], 'index': index,
                          'height': counts[name] * 100.0 / total}
                         for index, name in enumerate(series, start=1)
                         if counts[name]],
        })

    context['chart'] = chart
    context['chart_series'] = list(enumerate(series, start=1))
    context['chart_peak'] = peak
    context['chart_first_day'] = chart[0]['day'] if chart else None
    context['chart_last_day'] = chart[-1]['day'] if chart else None

    return render(request, 'ports/dashboard.html', context)


def build_env(request):
    context = {}

    context['navbar_fallout_be'] = 'active'

    fallout_env = Fallout.objects.all().values('env').annotate(total=Count('env'), total_ports=Count('port', distinct=True)).order_by('env')

    context['fallout_env'] = fallout_env

    return render(request, 'ports/build_env.html', context)


def maintainer(request):
    context = {}

    context['navbar_fallout_mt'] = 'active'

    maintainers = Fallout.objects.all().values('maintainer').annotate(total=Count('maintainer'), total_ports=Count('port', distinct=True)).order_by('-total')
    context['fallout_maintainers'] = maintainers

    return render(request, 'ports/maintainer.html', context)

class FalloutListView(RegexFilterMixin, ListView):
    paginate_by = 50
    model = Fallout
    ordering = ['-date']

    def get_queryset(self):
        maintainer = self.request.GET.get('maintainer', '').strip()
        port = self.request.GET.get('port', '').strip()
        env = self.request.GET.get('env', '').strip()
        category = self.request.GET.get('category', '').strip()
        flavor = self.request.GET.get('flavor', '').strip()
        categories = self.request.GET.getlist('categories')

        try:
            query = build_filter('maintainer', maintainer, 'istartswith')

            if port:
                query.add(build_filter('port__origin', port, 'icontains'), Q.AND)

            if env:
                query.add(build_filter('env', env, 'icontains'), Q.AND)

            if category:
                query.add(build_filter('category', category, 'iexact'), Q.AND)

            if flavor:
                query.add(build_filter('flavor', flavor, 'icontains'), Q.AND)
        except InvalidRegexError as error:
            self.filter_error = str(error)
            return Fallout.objects.none()

        if categories:
            query.add(Q(port__categories__name__in=categories), Q.AND)

        queryset = Fallout.objects.filter(query).select_related('port').order_by('-date')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar_fallout'] = 'active'
        context['form_maintainer'] = self.request.GET.get('maintainer', '')
        context['form_port'] = self.request.GET.get('port', '')
        context['form_env'] = self.request.GET.get('env', '')
        context['form_category'] = self.request.GET.get('category', '')
        context['form_flavor'] = self.request.GET.get('flavor', '')
        context['form_categories'] = self.request.GET.getlist('categories')
        context['categories'] = Category.objects.all().order_by('name')
        context['has_filter'] = any([context['form_maintainer'], context['form_port'],
                                     context['form_env'], context['form_category'],
                                     context['form_flavor'], context['form_categories']])
        return context


class FalloutDetailView(DetailView):
    model = Fallout
    template_name = 'ports/fallout_detail.html'


class PortListView(RegexFilterMixin, ListView):
    paginate_by = 50
    model = Port
    ordering = ['origin']

    def get_queryset(self):
        maintainer = self.request.GET.get('maintainer', '').strip()
        port = self.request.GET.get('port', '').strip()

        try:
            query = build_filter('maintainer', maintainer, 'istartswith')
            query.add(build_filter('origin', port, 'icontains'), Q.AND)
        except InvalidRegexError as error:
            self.filter_error = str(error)
            return Port.objects.none()

        from_date = dtz.now() - timedelta(days=30)
        query.add(Q(fallout__date__gte=from_date), Q.AND)

        queryset = Port.objects.filter(query).annotate(fcount=Count('fallout')).order_by('-fcount')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar_list'] = 'active'
        context['form_maintainer'] = self.request.GET.get('maintainer', '')
        context['form_port'] = self.request.GET.get('port', '')
        context['has_filter'] = any([context['form_maintainer'], context['form_port']])
        return context


class PortDetailView(DetailView):
    model = Port
    template_name = 'ports/port_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar_list'] = 'active'
        port_pk = self.kwargs.get('pk', None)
        context['fallout_list'] = Fallout.objects.filter(port=port_pk).order_by('-date')[:50]
        return context


class ServerListView(ListView):
    paginate_by = 50
    model = Server
    ordering = ['name']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar_server'] = 'active'
        return context


def about(request):
    context_dict = {'navbar_about':'active'}
    return render(request, 'ports/about.html', context_dict)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Categories.
    """
    search_fields = ['name']
    filter_backends = (filters.SearchFilter,)
    pagination_class = CappedLimitOffsetPagination
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer


class PortViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Port's.
    """
    search_fields = ['origin', 'maintainer']
    filter_backends = (filters.SearchFilter,)
    pagination_class = CappedLimitOffsetPagination
    queryset = Port.objects.all().prefetch_related('categories').order_by('origin')
    serializer_class = PortSerializer


class FalloutViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Fallout's.
    """
    search_fields = ['maintainer', 'port__origin', 'env', 'category']
    filter_backends = (filters.SearchFilter,)
    pagination_class = CappedLimitOffsetPagination
    queryset = (Fallout.objects.all()
                .select_related('port')
                .prefetch_related('port__categories')
                .order_by('-date'))
    serializer_class = FalloutSerializer
