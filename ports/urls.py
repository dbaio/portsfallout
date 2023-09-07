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

"""ports URL Configuration"""

from django.urls import include, path
from ports import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'category', views.CategoryViewSet)
router.register(r'port', views.PortViewSet)
router.register(r'fallout', views.FalloutViewSet)

# TEMPLATE TAGGING
app_name = 'ports'

urlpatterns = [
    path('', views.dashboard, name='index'),
    path('build_env', views.build_env, name='build_env'),
    path('fallout', views.FalloutListView.as_view(), name='fallout'),
    path('fallout/<int:pk>/', views.FalloutDetailView.as_view(), name='fdetail'),
    path('port', views.PortListView.as_view(), name='list'),
    path('port/<int:pk>/', views.PortDetailView.as_view(), name='detail'),
    path('server', views.ServerListView.as_view(), name='server'),
    path('about', views.about, name='about'),
    path('api/', include(router.urls)),
]
