# Copyright (c) 2020 Danilo G. Baio <dbaio@bsd.com.br>
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

from django.shortcuts import render
from django.views.generic import View, TemplateView, ListView, DetailView
from django.db.models import Count, Q
from ports.models import Port, Category, Fallout


def dashboard(request):
    context = {'navbar_pesquisa':'active'}

    fallout_count = Fallout.objects.count()
    context['fallout_count'] = fallout_count

    fallout_cat = Fallout.objects.all().values('category').annotate(total=Count('category')).order_by('-total')
    context['fallout_cat'] = fallout_cat

    fallout_env = Fallout.objects.all().values('env').annotate(total=Count('env')).order_by('-total')
    context['fallout_env'] = fallout_env

    fallout_main = Fallout.objects.all().values('maintainer').annotate(total=Count('maintainer')).order_by('-total')[:25]
    context['fallout_main'] = fallout_main

    fallout_recent = Fallout.objects.all().values().order_by('-date')[0]
    context['fallout_recent'] = fallout_recent

    fallout_oldest = Fallout.objects.all().values().order_by('date')[0]
    context['fallout_oldest'] = fallout_oldest

    return render(request, 'ports/dashboard.html', context)


class FalloutListView(ListView):
    paginate_by = 50
    model = Fallout
    ordering = ['-date']

    def get_queryset(self):
        maintainer = self.request.GET.get('maintainer', '')
        port = self.request.GET.get('port', '')
        env = self.request.GET.get('env', '')
        category = self.request.GET.get('category', '')

        query = Q(maintainer__icontains=maintainer)
        query.add(Q(port__origin__icontains=port), Q.AND)
        query.add(Q(env__icontains=env), Q.AND)
        query.add(Q(category__icontains=category), Q.AND)

        # categories 8 == Python
        #query.add(Q(port__categories__in=[ 8 ]), Q.AND)

        queryset = Fallout.objects.filter(query).order_by('-date')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar_fallout'] = 'active'
        context['form_maintainer'] = self.request.GET.get('maintainer', '')
        context['form_port'] = self.request.GET.get('port', '')
        context['form_env'] = self.request.GET.get('env', '')
        context['form_category'] = self.request.GET.get('category', '')
        return context


class FalloutDetailView(DetailView):
    model = Fallout
    template_name = 'ports/fallout_detail.html'


class PortListView(ListView):
    paginate_by = 50
    model = Port
    ordering = ['origin']

    def get_queryset(self):
        maintainer = self.request.GET.get('maintainer', '')
        port = self.request.GET.get('port', '')
        query = Q(maintainer__icontains=maintainer)
        query.add(Q(origin__icontains=port), Q.AND)
        queryset = Port.objects.filter(query).order_by('origin')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar_list'] = 'active'
        context['form_maintainer'] = self.request.GET.get('maintainer', '')
        context['form_port'] = self.request.GET.get('port', '')
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


def about(request):
    context_dict = {'navbar_about':'active'}
    return render(request, 'ports/about.html', context_dict)

