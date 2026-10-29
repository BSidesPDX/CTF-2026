import ed25519
import requests
import jwt
import base64
import json

# CHANGE THESE
authserver = "https://twisted-auth.chals.ctf.bsidespd.xyz"
contentserver = "https://twisted.chals.ctf.bsidespd.xyz"

username = "first"
password = "b2g3h48d4WX47Uup4qhWwa2mgjxK3zJ5"

# username "edwards"
target = "1"

# See valid JWT
r1 = requests.post(authserver + '/login/', data={'username':username,'password':password})
if r1.ok:
    token = r1.json()["token"]
    header, payload, signature = token.split('.')


# Obtain the public key
r2 = requests.get(authserver + '/.well-known/jwks.json')
if r2.ok:
    public_key = r2.json()['x']
    pk = base64.b64decode(public_key)[12:]

# Forge for the new user
#  Attack vaguely looks like:
#  sk = 1 (a=1)
#  G = pk
#  pk = pk

def attacker_signature(m, sk, pk, G):
    """Sign m. G is the generator point [x, y] used for the computation;
    pk must have been produced with the same G (see publickey)."""
    h = ed25519.H(sk)
    # a = 2**(b - 2) + sum(2**i * bit(h, i) for i in range(3, b - 2))
    a = 1
    r = ed25519.Hint(h[ed25519.b // 8:ed25519.b // 4] + m)
    R = ed25519.scalarmult(G, r)
    S = (r + ed25519.Hint(ed25519.encodepoint(R) + pk + m) * a) % ed25519.l
    return ed25519.encodepoint(R) + ed25519.encodeint(S)

def attacker_publickey(sk, G):
    h = ed25519.H(sk)
    # a = 2**(b - 2) + sum(2**i * bit(h, i) for i in range(3, b - 2))
    a = 1
    A = ed25519.scalarmult(G, a)
    return ed25519.encodepoint(A)


payload_d = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
payload_d['G'] = base64.b64encode(pk).decode('ASCII')
payload_d['sub'] = target

m_str = header + "." + base64.urlsafe_b64encode(json.dumps(payload_d).encode('ASCII')).decode('ASCII')
m = m_str.encode('ASCII')
fake_sk = pk # Just need an arbitrary point on the curve
print(f"len sk is {len(fake_sk)}")

fake_G = ed25519.decodepoint(pk)
# fake_G = ed25519.decodepoint(base64.b64decode(payload_d['G']))
fake_pk = attacker_publickey(fake_sk, fake_G)
# fake_pk = pk
s = attacker_signature(m, fake_sk, fake_pk, fake_G)
# s = ed25519.signature(m, fake_sk, fake_pk, fake_G)

new_token = m_str + "." + base64.urlsafe_b64encode(s).decode('ASCII')
# print(new_token)

ed25519.checkvalid(s, m, pk, fake_G)

# Send forged token to the server
r3 = requests.get(contentserver + '/emails/', headers={'Authorization': f"Bearer {new_token}"})
print(r3.text)
