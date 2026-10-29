#!/usr/bin/env python3
"""Reproducible solver for 2026/crypto/order-66.

Chain:
  1. intercept.mp3 is a voice transmission: Obi-Wan's Attack of the Clones
     report from Kamino. It names the bounty hunter "Jango Fett". That name is
     the GPG symmetric passphrase. (Transcribe the audio with any speech-to-text
     tool; this solver takes the recovered passphrase as a constant.)
  2. transmission.gpg decrypts to a pcap of one TLS 1.2 session to
     stardust.scarif.empire.mil.
  3. The session uses TLS_RSA_WITH_AES_128_CBC_SHA (static RSA key exchange).
     The server certificate's RSA modulus is 512-bit and factors as
     N = 317 * q, so the private key is trivially recoverable and the RSA
     ClientKeyExchange premaster secret decrypts.
  4. The handshake negotiated extended_master_secret (RFC 7627) and
     encrypt_then_mac (RFC 7366):
        master = PRF(pms, "extended master secret", SHA256(CH..CKE), 48)
        record = IV[16] || AES-CBC(content || pad) || HMAC-SHA1[20]
     Deriving the key block and decrypting the application records yields the
     HTTP response carrying the flag.

Dependencies: gpg, openssl, python3 (standard library only).
Usage: solve.py [path-to-ISB-1138.ZIP]   (default: ../ISB-1138.ZIP)
"""
import hashlib
import hmac
import os
import re
import subprocess
import sys
import tempfile
import zipfile

PASSPHRASE = "Jango Fett"   # the bounty hunter named in intercept.mp3


# ---------------------------------------------------------------- pcap parsing
def pcap_tcp_payloads(data):
    """Yield TCP payloads (in capture order) from a classic Ethernet pcap."""
    if data[:4] not in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4"):
        raise ValueError("not a classic pcap")
    off = 24  # global header
    while off + 16 <= len(data):
        incl = int.from_bytes(data[off + 8:off + 12], "little")
        pkt = data[off + 16:off + 16 + incl]
        off += 16 + incl
        if len(pkt) < 14 + 20:
            continue
        ihl = (pkt[14] & 0x0F) * 4
        ip = pkt[14:]
        if ip[9] != 6:            # not TCP
            continue
        tcp = ip[ihl:]
        doff = (tcp[12] >> 4) * 4
        payload = tcp[doff:]
        if payload:
            yield payload


def tls_records(payload):
    """Split a TCP payload into (content_type, fragment) TLS records."""
    off, out = 0, []
    while off + 5 <= len(payload):
        ct = payload[off]
        ln = int.from_bytes(payload[off + 3:off + 5], "big")
        out.append((ct, payload[off + 5:off + 5 + ln]))
        off += 5 + ln
    return out


# ------------------------------------------------------------------- TLS 1.2
def p_hash(secret, seed, n):
    out, a = b"", seed
    while len(out) < n:
        a = hmac.new(secret, a, hashlib.sha256).digest()
        out += hmac.new(secret, a + seed, hashlib.sha256).digest()
    return out[:n]


def prf(secret, label, seed, n):
    return p_hash(secret, label + seed, n)


def etm_cbc_decrypt(frag, enc_key):
    """encrypt-then-MAC CBC record: IV[16] || ciphertext || HMAC-SHA1[20]."""
    iv, ct = frag[:16], frag[16:-20]
    pt = subprocess.run(
        ["openssl", "enc", "-aes-128-cbc", "-d", "-nopad",
         "-K", enc_key.hex(), "-iv", iv.hex()],
        input=ct, capture_output=True).stdout
    return pt[:-(pt[-1] + 1)]      # strip CBC padding


# ---------------------------------------------------------------- RSA / cert
def cert_modulus(cert_der):
    p = subprocess.run(
        ["openssl", "x509", "-inform", "DER", "-noout", "-modulus"],
        input=cert_der, capture_output=True)
    return int(p.stdout.decode().strip().split("=", 1)[1], 16)


def recover_private_d(n, e=65537):
    for p in range(3, 1 << 20, 2):
        if n % p == 0:
            q = n // p
            return pow(e, -1, (p - 1) * (q - 1))
    raise ValueError("no small factor found")


def pkcs1_unpad(block):
    idx = block.find(b"\x00", 2)
    return block[idx + 1:]


# --------------------------------------------------------------------- driver
def main():
    zip_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "ISB-1138.ZIP")

    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zip_path) as z:
            z.extract("transmission.gpg", td)
        gpg_path = os.path.join(td, "transmission.gpg")
        pcap = subprocess.run(
            ["gpg", "--batch", "--yes", "--quiet", "--pinentry-mode", "loopback",
             "--passphrase", PASSPHRASE, "-d", gpg_path],
            capture_output=True).stdout
    if pcap[:4] != b"\xd4\xc3\xb2\xa1":
        raise SystemExit("GPG decryption failed")

    payloads = list(pcap_tcp_payloads(pcap))
    records = [(ct, frag) for pl in payloads for (ct, frag) in tls_records(pl)]

    # Handshake messages ClientHello..ClientKeyExchange = type-22 records
    # before the first ChangeCipherSpec (the later Finished records are
    # encrypted and must be excluded).
    handshakes, app = [], []
    seen_ccs = False
    for ct, frag in records:
        if ct == 20:
            seen_ccs = True
        elif ct == 22 and not seen_ccs:
            handshakes.append(frag)
        elif ct == 23:
            app.append(frag)

    client_hello, server_hello = handshakes[0], handshakes[1]
    certificate, cke = handshakes[2], handshakes[-1]
    client_random = client_hello[6:38]
    server_random = server_hello[6:38]

    # Certificate message: type(1) len(3) certs_len(3) cert_len(3) cert_der...
    cert_len = int.from_bytes(certificate[7:10], "big")
    cert_der = certificate[10:10 + cert_len]
    n = cert_modulus(cert_der)

    # ClientKeyExchange (RSA): type(1) len(3) epms_len(2) epms
    epms = cke[6:]
    d = recover_private_d(n)
    pms = pkcs1_unpad(pow(int.from_bytes(epms, "big"), d, n).to_bytes(
        (n.bit_length() + 7) // 8, "big"))

    # extended_master_secret + encrypt_then_mac
    session_hash = hashlib.sha256(b"".join(handshakes)).digest()
    master = prf(pms, b"extended master secret", session_hash, 48)
    kb = prf(master, b"key expansion", server_random + client_random, 72)
    ckey, skey = kb[40:56], kb[56:72]

    request = etm_cbc_decrypt(app[0], ckey)
    response = etm_cbc_decrypt(app[1], skey)
    print("N = 317 *", n // 317)
    print("--- request ---\n%s" % request.decode("latin-1"))
    print("--- response ---\n%s" % response.decode("latin-1"))

    flag = re.search(rb"pdx\{[^}]*\}", response)
    print("\nFLAG:", flag.group().decode() if flag else "not found")
    return 0 if flag else 1


if __name__ == "__main__":
    sys.exit(main())
