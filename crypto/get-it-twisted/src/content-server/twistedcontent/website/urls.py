# URL configuration for twistedauth project.


from django.contrib import admin
from django.urls import path, include

from .views import *

urlpatterns = [
    path('', Root.as_view(), name='root'),
    path('emails/', Emails.as_view(), name='emails-partial'),
    path('login/', Login.as_view(), name='login-partial'),
    path('debug/', Debug.as_view(), name='debug'),
]
