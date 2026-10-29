from django.shortcuts import render
from django.views import View
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from .models import *
from twistedcontent.settings import TWISTED_AUTH_URL

# Create your views here.

class Debug (View):
    def get (self, request):
        if request.user:
            return JsonResponse({"ok": True, "user": request.user})
        else:
            return JsonResponse({"ok": False, "user": None})

class Root (View):
    def get (self, request):
        # Unauthenticated base. "SPA app"
        return render (request, "index.html", {})

class Emails (View):
    def get (self, request):
        if request.user:
            # render emails for the user
            emails = EmailModel.objects.filter(user_id=request.user)
            return render (request, "partials/emails.html", {"emails": emails})
        else:
            # render login page
            return render (request, "partials/login.html", {"twisted_auth_url": TWISTED_AUTH_URL}, status=401)

class Login (View):
    def get (self, request):
        return render (request, "partials/login.html", {"twisted_auth_url": TWISTED_AUTH_URL})
