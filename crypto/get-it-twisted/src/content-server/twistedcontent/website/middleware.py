# Middleware
import requests
import jwt
from jwt import PyJWKClient
from . import ed25519
import base64
import json
from twistedcontent.settings import TWISTED_AUTH_URL
    

def validate_token (token):
    #THE SAUCE!!!
    header, payload, signature = token.split('.')
    s = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    m = (header + "." + payload).encode('ASCII')

    payload_d = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    G = ed25519.decodepoint(base64.b64decode(payload_d['G']))

    # Get the public key
    r = requests.get(f"{TWISTED_AUTH_URL}/.well-known/jwks.json")
    if not r.ok:
        return None
    public_key = r.json()['x']
    pk = base64.b64decode(public_key)[12:]

    try:
        ed25519.checkvalid(s, m, pk, G)
    except:
        return None
    else:
        # return payload_d['sub'] if 'sub' in payload_d else None
        sub = int(payload_d['sub'])
        print(sub)
        return sub

class AuthorizationTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if auth_header:
            token = auth_header.split(' ')[-1]
            request.user = validate_token(token)
        else:
            request.user = None

        return self.get_response(request)
