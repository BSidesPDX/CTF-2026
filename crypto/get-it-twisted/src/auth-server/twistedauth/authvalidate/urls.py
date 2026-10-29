# URL configuration for twistedauth project.


from django.contrib import admin
from django.urls import path, include

from .views import *

urlpatterns = [
    path('.well-known/jwks.json', jwks.as_view(), name='jwks'),
    path('robots.txt', robots.as_view(), name='robots'),
    path('login/', Login.as_view(), name='login'),
]
