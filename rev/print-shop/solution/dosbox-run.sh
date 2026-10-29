#!/bin/bash
# Run a DOS program headless under DOSBox-X, with LPT1 wired one of three ways.
#
#   dosbox-run.sh PROGRAM.EXE MODE [OUTDIR]
#
# MODE:
#   none     no parallel port configured (what a stock install gives a player)
#   file     raw byte capture to OUTDIR/lpt1.prn, for solver-escp.py
#   printer  DOSBox-X's emulated Epson, rendering portrait letter pages to
#            OUTDIR as 180 dpi PNGs, the banner running down them sideways
# The program's console output lands in OUTDIR/stdout.txt and DOSBox-X's own
# in OUTDIR/dosbox.log. OUTDIR defaults to the challenge's build/run-MODE.
#
# DOSBOX_X names the binary (default: dosbox-x on PATH). For a .deb unpacked
# without installing it, point DOSBOX_X at its usr/bin/dosbox-x and put its
# usr/lib/x86_64-linux-gnu on LD_LIBRARY_PATH.
set -euo pipefail

prog=$(realpath "$1")
mode=$2
out=$(realpath -m "${3:-$(dirname "$0")/../build/run-${mode}}")
dbx=$(command -v "${DOSBOX_X:-dosbox-x}") || {
    echo "dosbox-run.sh: DOSBox-X not found; set DOSBOX_X" >&2
    exit 2
}
mkdir -p "${out}"
rm -f "${out}"/*.prn "${out}"/*.png "${out}/stdout.txt"

export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy

case "${mode}" in
    none)    par="parallel1=disabled" ;;
    file)    par="parallel1=file file:${out}/lpt1.prn" ;;
    printer) par="parallel1=printer" ;;
    *) echo "dosbox-run.sh: unknown mode ${mode}" >&2; exit 2 ;;
esac

# The emulated printer needs DOSBox-X's resource files, which an unpacked .deb
# keeps beside the binary rather than where DOSBox-X looks by default.
share=$(dirname "${dbx}")/../share/dosbox-x
defaultdir=()
[ -d "${share}" ] && defaultdir=(-defaultdir "$(realpath "${share}")")

conf=${out}/dosbox.conf
cat > "${conf}" <<EOF
[sdl]
output=surface
[dosbox]
machine=svga_s3
memsize=4
quit warning=false
[cpu]
cycles=max
[mixer]
nosound=true
[parallel]
${par}
[printer]
printer=true
dpi=180
width=85
height=110
printoutput=png
multipage=false
docpath=${out}
timeout=1000
[autoexec]
EOF

timeout 120 "${dbx}" -conf "${conf}" "${defaultdir[@]}" -nogui -nomenu -fastlaunch \
    -c "mount c \"$(dirname "${prog}")\"" -c "c:" \
    -c "$(basename "${prog}") > C:\\STDOUT.TXT" -c "exit" \
    >"${out}/dosbox.log" 2>&1 || echo "dosbox-run.sh: dosbox-x exited $?" >&2
mv -f "$(dirname "${prog}")/STDOUT.TXT" "${out}/stdout.txt" 2>/dev/null || true
ls -la "${out}"
[ -f "${out}/stdout.txt" ] && cat "${out}/stdout.txt"
