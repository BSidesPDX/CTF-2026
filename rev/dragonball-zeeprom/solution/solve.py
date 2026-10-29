#!/usr/bin/env python3
"""
Solver for "Dragonball Zeeprom", version 2 (ZEEPROM-2.prc).

Same Palm m515 Scouter, hardened against the four-byte brute force that broke
v1. Two changes in the one code resource:

1. The environment gate no longer pins the OEM device ID. It still requires
   Palm OS 4.1 (sysFtrNumROMVersion low word == 1040) and a DragonBall VZ
   (sysFtrNumProcessorID low word == 3) and a programmed serial, but
   `FtrGet('psys', 21)` (sysFtrNumOEMDeviceID) is read and fed into the key
   without being checked. So the device ID is now the unknown that unlocks the
   flag, and only the right device decrypts it.

2. The key is stretched. The 16-byte seed

       seed = [psys1 hi word][psys2 hi word][psys21 full][00 x7][serial = 1]
            =  04 10          00 03          <device ID>   00..   01

   is AES-decrypted 257 times under the key "ScouterZeeprom!!" (ECB, i.e. CBC
   with a zero IV over one block). The result is the AES key used to
   CBC-decrypt the 48-byte flag blob with IV "ZeekiVect0rF1ll!".

The high words 04 10 and 00 03 follow from the gated OS version (4.1) and
processor (VZ); they are not secret. Only the device ID varies, so recovery is
an enumeration of real Palm OS 4.1 / VZ OEM device IDs, each costing 257 AES
decrypts (the point of the stretch: a blind 2^32 byte-sweep now takes hours,
while the few dozen real device IDs take an instant). The Palm m515's ID "lith"
wins:

    pdx{a_p0w3r_l3v3l_OVER_68000!!!}
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import original as v1   # reuse _expand, _inv_cipher, cbc_decrypt, code_resource

# Palm OEM device IDs (company 'palm'). OS 4.1 / DragonBall VZ models first.
DEVICE_IDS = [b"lith", b"hbbs", b"sky1", b"trnd", b"ecty", b"stuj",
              b"Zir4", b"Cctl", b"Frg1", b"Frg2", b"MT64"]


def derive_key(seed, stretch_w, rounds=257):
    s = seed
    for _ in range(rounds):
        s = v1._inv_cipher(s, stretch_w)
    return s


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("prc", nargs="?",
                    default=os.path.join(here, "..", "ZEEPROM.prc"))
    args = ap.parse_args()

    code = v1.code_resource(args.prc, 1)
    base = b"ScouterZeeprom!!"
    iv = b"ZeekiVect0rF1ll!"
    assert base in code and iv in code
    iv_off = code.find(iv)
    blob = code[iv_off + 16:iv_off + 16 + 48]
    stretch_w = v1._expand(base)

    # OS 4.1 -> ROM-version high word 0x0410; VZ -> processor-ID high word 0x0003.
    prefix = bytes([0x04, 0x10, 0x00, 0x03])
    suffix = bytes(7) + bytes([0x01])     # 7 zero bytes, then serial-present flag

    for dev in DEVICE_IDS:
        seed = prefix + dev + suffix
        key = derive_key(seed, stretch_w)
        pt = v1.cbc_decrypt(blob, key, iv)
        if pt[:4] == b"pdx{":
            pad = pt[-1]
            flag = pt[:len(pt) - pad]
            print("device ID :", dev.decode("latin1"), "(Palm m515)" if dev == b"lith" else "")
            print("seed      :", seed.hex())
            print("key       :", key.hex())
            print("FLAG      :", flag.decode("latin1"))
            return 0
    print("no device ID in the list decrypted the blob", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
