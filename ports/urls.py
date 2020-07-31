"""ports URL Configuration"""

from django.urls import path
from ports import views

# TEMPLATE TAGGING
app_name = 'ports'

urlpatterns = [
    path('', views.dashboard, name='index'),
    path('fallout', views.FalloutListView.as_view(), name='fallout'),
    path('fallout/<int:pk>/', views.FalloutDetailView.as_view(), name='fdetail'),
    path('port', views.PortListView.as_view(), name='list'),
    path('port/<int:pk>/', views.PortDetailView.as_view(), name='detail'),
    path('about', views.about, name='about'),
]
