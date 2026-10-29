#!/usr/bin/env python3
"""
Solver for "Passgen" (BSidesPDX 2026, rev).

`passgen` is a small, statically linked, hand-written x86-64 binary (one
`_start`, no libc). Its logic:

  s = time(NULL) % 60
  print "suggested passphrase: " + phrases[s]       # a lookup table of 60 phrases
  ... except when s == 26, where it prints the flag instead.

The flag branch builds `pdx{...}` from a hardcoded string in .rodata, replacing
each space with '_'. That string sits immediately after the NUL-terminated
prompt "suggested passphrase: " in .rodata:

  "time weights four nobody"   (a pun on "time waits for no one")

So the flag is recovered statically, with no need to run the binary at the right
second:

  pdx{time_weights_four_nobody}

This reads the unmodified binary.

Usage: python3 -I solve.py [path-to-passgen]
"""
import os
import sys

PROMPT = b"suggested passphrase: \x00"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "passgen")
    data = open(path, "rb").read()

    i = data.find(PROMPT)
    if i < 0:
        print("prompt string not found", file=sys.stderr)
        return 1
    start = i + len(PROMPT)                      # the flag phrase follows the prompt
    phrase = data[start:data.index(b"\x00", start)].decode("latin1")

    print("trigger        : time(NULL) % 60 == 26")
    print("flag phrase    :", repr(phrase))
    print("FLAG           :", "pdx{%s}" % phrase.replace(" ", "_"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
