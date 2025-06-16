from django.urls import path
from apps.core.views import view

urlpatterns = [path('panel/', view, name='panel')]