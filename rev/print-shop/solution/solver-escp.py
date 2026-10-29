#!/usr/bin/env python3
"""Render a captured Epson ESC/P print job to an image: the reference solution.

    solver-escp.py LPT1.PRN OUT.png [--read]
    solver-escp.py LPT1.PRN OUT.pbm

Capture the job by running PRNTSHOP.EXE under DOSBox-X with
    [parallel]
    parallel1=file file:lpt1.prn
then render it here. --read rotates the strip a quarter turn so the banner reads
left to right. A .pbm output is the raw paper-orientation bitmap, one bit per dot.

Handles what 8-pin banner software of the era sends: text (skipped), CR, LF, FF,
ESC @, line spacing (ESC 0/1/2/3/A, ESC J), and 8-pin bit images (ESC K/L/Y/Z
and ESC * with modes 0-6). Vertical positions are kept in 1/216" and mapped to
1/72" pin rows; columns are kept in whatever density the job used, which for a
job that never mixes densities is exact.

Standard library only.
"""
import argparse
import struct
import sys
import zlib

ESC = 0x1B
EIGHT_PIN = {0, 1, 2, 3, 4, 5, 6}
SHORTHAND = {ord('K'): 0, ord('L'): 1, ord('Y'): 2, ord('Z'): 3}


def render(job):
    """Return (rows, text) where rows maps pin row -> {column: 1}."""
    rows = {}
    text = []
    spacing = 36                    # 1/6" in 1/216"
    y = x = 0
    modes = set()
    i = 0

    def arg(k):
        if i + k >= len(job):
            sys.exit(f'truncated escape sequence at offset {i}')
        return job[i + k]

    while i < len(job):
        b = job[i]
        if b == ESC:
            cmd = arg(1)
            if cmd == ord('@'):
                spacing, i = 36, i + 2
            elif cmd == ord('0'):
                spacing, i = 27, i + 2
            elif cmd == ord('1'):
                spacing, i = 21, i + 2
            elif cmd == ord('2'):
                spacing, i = 36, i + 2
            elif cmd == ord('3'):
                spacing, i = arg(2), i + 3
            elif cmd == ord('A'):
                spacing, i = arg(2) * 3, i + 3
            elif cmd == ord('J'):
                y, i = y + arg(2), i + 3
            elif cmd in SHORTHAND or cmd == ord('*'):
                if cmd == ord('*'):
                    mode, n, hdr = arg(2), arg(3) | arg(4) << 8, 5
                    if mode not in EIGHT_PIN:
                        sys.exit(f'ESC * mode {mode} (24-pin) is not handled')
                else:
                    mode, n, hdr = SHORTHAND[cmd], arg(2) | arg(3) << 8, 4
                modes.add(mode)
                data = job[i + hdr:i + hdr + n]
                row0 = y // 3
                for col, byte in enumerate(data):
                    for pin in range(8):
                        if byte & (0x80 >> pin):
                            rows.setdefault(row0 + pin, {})[x + col] = 1
                x += n
                i += hdr + n
            else:
                sys.exit(f'unhandled ESC {cmd:#04x} at offset {i}')
        elif b == 0x0D:
            x, i = 0, i + 1
        elif b == 0x0A:
            y, i = y + spacing, i + 1
        elif b == 0x0C:
            i += 1                  # continuous paper: the banner does not break
        elif 0x20 <= b < 0x7F:
            j = i
            while j < len(job) and 0x20 <= job[j] < 0x7F:
                j += 1
            text.append(job[i:j].decode('ascii'))
            i = j
        else:
            i += 1
    if len(modes) > 1:
        print(f'warning: mixed bit-image densities {sorted(modes)}; columns are '
              'not to a common scale', file=sys.stderr)
    return rows, text


def bitmap(rows):
    """Crop to the graphics: (width, height, list of rows of 0/1)."""
    if not rows:
        sys.exit('no bit-image graphics in this job')
    r0, r1 = min(rows), max(rows)
    width = max(max(cols) for cols in rows.values()) + 1
    return width, r1 - r0 + 1, [[rows.get(r, {}).get(c, 0) for c in range(width)]
                                for r in range(r0, r1 + 1)]


def rotate_ccw(width, height, px):
    return height, width, [[px[r][width - 1 - c] for r in range(height)]
                           for c in range(width)]


def write_pbm(path, width, height, px):
    with open(path, 'wb') as f:
        f.write(b'P4\n%d %d\n' % (width, height))
        for row in px:
            out = bytearray((width + 7) // 8)
            for c, v in enumerate(row):
                if v:
                    out[c >> 3] |= 0x80 >> (c & 7)
            f.write(out)


def write_png(path, width, height, px):
    raw = bytearray()
    for row in px:
        raw.append(0)
        raw += bytes(0 if v else 255 for v in row)

    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data +
                struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF))
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(bytes(raw), 9)))
        f.write(chunk(b'IEND', b''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    ap.add_argument('out')
    ap.add_argument('--read', action='store_true', help='rotate to read left to right')
    args = ap.parse_args()

    rows, text = render(open(args.job, 'rb').read())
    for t in text:
        print('text:', t)
    width, height, px = bitmap(rows)
    if args.read:
        width, height, px = rotate_ccw(width, height, px)
    if args.out.endswith('.pbm'):
        write_pbm(args.out, width, height, px)
    else:
        write_png(args.out, width, height, px)
    print(f'{args.out}: {width}x{height}')


if __name__ == '__main__':
    main()
