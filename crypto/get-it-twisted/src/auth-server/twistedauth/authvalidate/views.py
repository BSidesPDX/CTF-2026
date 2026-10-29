from django.shortcuts import render
from django.views import View
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from .forms import *
from django.contrib.auth import authenticate
import jwt

# Create your views here.
with open("private.pem") as f:
    private_key = f.read()



class jwks (View):
    def get(self, request):
        # TODO: make this coherent
        return JsonResponse({
        "kty": "OKP",
        "use": "sig",
        "kid": "keep-it-twisted",
        "alg": "EdDSA",
        "crv": "Ed25519",
        "x": "MCowBQYDK2VwAyEAxubLWv+Hbw61KiubtSk9yY4MBPI6q/tzyENNATuYoEc="
    })

class robots (View):
    def get(self, request):
        return HttpResponse("""User-agent: *
Disallow: /.well-known/jwks.json""", content_type="text/plain")


class Login (View):
    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user is not None:
                # return a JWT
                # TODO: edit iat and exp
                payload = {"sub": f"{user.pk}", "aud": "get-it-twisted", "iat": 0, "G": "WGZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmY="}
                header = {"kid": "get-it-twisted"}
                token = jwt.encode(payload, private_key, algorithm="EdDSA")

                return JsonResponse({'token': token}, status=200)

        # catchall for both if statements
        return JsonResponse({'errors': ['Invalid credentials.']}, status=400)