#!/usr/bin/env python3
"""
Solver for "Never Hesitate" (BSidesPDX 2026, rev).

The challenge is a bash "oracle" script. Stripped of theater, its flag logic is:

  * delay  = whole seconds you took to answer the prompt.
  * factor = smallest prime >= delay (clamp_token_factor; delay < 2 becomes 2).
  * phrase = words[(factor*k) % 1024] for k = 1..6.
  * base_factor = (( RANDOM > start )): RANDOM is at most 32767 and `start` is a
    ~1.7e9 unix timestamp, so this is always 0, which makes the answer substring
    ${answer:0:0} empty. The typed answer never affects the hash.
  * if sha256(phrase) == HASH, it prints pdx{phrase_with_underscores}.

So the flag depends only on `factor`, and only on `factor % 1024` (the index is
taken mod 1024). There are at most 1024 distinct phrases; brute all residues and
match the embedded HASH. The winning residue is 37 (a prime), which a player
reaches by taking 32..37 seconds to answer, so nextprime(delay) = 37. Answering
instantly ("never hesitate") gives factor = 2 and the wrong phrase: the title is
the misdirection, and the recovered line "no fate but what we make" is the point.

This reads the unmodified script; it never runs it.

Usage: python3 -I solve.py [path-to-never-hesitate]
"""
import hashlib
import os
import re
import sys

TABLE_SIZE = 1024
NUM_WORDS = 6


def is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, "..", "never-hesitate")
    src = open(path, encoding="utf-8").read()

    words = re.findall(r'"([^"]*)"', re.search(r"words=\((.*?)\)", src, re.S).group(1))
    target = re.search(r'HASH="([0-9a-f]+)"', src).group(1)
    assert len(words) == TABLE_SIZE, f"expected {TABLE_SIZE} words, got {len(words)}"

    for factor in range(TABLE_SIZE):
        phrase = " ".join(words[(factor * k) % TABLE_SIZE]
                          for k in range(1, NUM_WORDS + 1))
        if hashlib.sha256(phrase.encode()).hexdigest() == target:
            lo = gap_below(factor) + 1         # nextprime(delay) == factor for
            print("factor (mod 1024):", factor, "(prime)" if is_prime(factor) else "")
            print("reach by answering in", f"{lo}..{factor}",
                  "seconds (so nextprime(delay) == factor)")
            print("phrase           :", phrase)
            print("FLAG             :", "pdx{%s}" % phrase.replace(" ", "_"))
            return 0
    print("no residue matched HASH", file=sys.stderr)
    return 1


def gap_below(p):
    """Largest prime strictly below p (0 if none)."""
    n = p - 1
    while n >= 2 and not is_prime(n):
        n -= 1
    return n if n >= 2 else 0


if __name__ == "__main__":
    sys.exit(main())
