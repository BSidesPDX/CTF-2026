#
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class LoginForm(forms.Form):
    username = forms.CharField (max_length=1000)
    password = forms.CharField (max_length=1000)