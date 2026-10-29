#!/usr/bin/env bash

set -o noglob

declare -a tape jumps program
declare -i p ip depth

function abort {
    local cmd
    cmd="${1}"
    echo -e "INVALID OP: ${cmd}\n\nTERMINATING\n\nTHIS EVENT HAS BEEN REPORTED"
    exit 67
}

function validate {
    local cmd
    local -a banned
    banned=("ar" "bg" "cp" "cd" "dc" "dd" "df" "du" "fc" "fg" "hd" "id" "ip" "ln" "ls" "mt" "mv" "nc" "nl" "od" "ps" "rm" "rx" "sh" "su" "sv" "tr" "vi" "wc")
    cmd="${1}"
    opLen=${#cmd}
    if test $opLen -gt 2; then
        abort "${cmd}"
    fi
    for banned_cmd in "${banned[@]}"; do
        test "${cmd}" = "${banned_cmd}" && abort "${cmd}"
    done
}

for ((i=0; i < 2048; i++)) do
    tape[i]=0;
done
p=0
ip=0
depth=0

# ^
# Move the data pointer up the tape 1 cell.
function ^ {
    p=$((p - 1))
    ip=$((ip + 1))
}

# v
# Move the data pointer down the tape 1 cell.
function v {
    p=$((p + 1))
    ip=$((ip + 1))
}

# +
# Increment the current cell.
function + {
    tape[p]=$((tape[p] + 1))
    ip=$((ip + 1))
}

# -
# Decrement the current cell.
function - {
    tape[p]=$((tape[p] - 1))
    ip=$((ip + 1))
}

# ,
# Read a single char into the current cell.
function , {
    read -r -N 1 c
    tape[p]=$(printf '%d' "'$c")
    ip=$((ip + 1))
}

# .
# Print current cell as char.
function . {
    echo -ne $(printf '\\x%x' "${tape[$p]}")
    ip=$((ip + 1))
}

# *
# Debug print the tape.
function * {
    echo "p=${p}"
    echo "tape=${tape[*]}"
    ip=$((ip + 1))
}

function jump {
    while test $1 -lt $depth ; do
        ip=$((ip + 1))
        if test ${program[$ip]} = ":]" ; then
            depth=$((depth - 1))
        fi
    done
}

# [
# Jump forward to matching ] if current cell is zero.
function [ {
    test $DEBUG && echo "DEBUG: [ at depth=${depth}"
    test $DEBUG && echo "p = ${p}"
    test $DEBUG && echo "tape: ${tape[*]}"
    test $DEBUG && echo "ip = ${ip}"
    test $DEBUG && echo "prog: ${program[*]}"

    local _d
    _d=$((depth))
    jumps[depth]=$((ip))
    depth=$((depth + 1))
    case $((tape[p])) in
        (0)
            jump $_d
            ip=$((ip + 1))
            ;;
        (*)
            ip=$((ip + 1))
            ;;
    esac
}

# ]
# Jump back to matching [ if current cell is not zero.
function ] {
    depth=$((depth - 1))
    test $DEBUG && echo "DEBUG: ] at depth=${depth}"
    if test ${tape[$p]} -ne 0; then
        ip=$((jumps[depth]))
    else
        ip=$((ip + 1))
    fi
}

# h
# Print help for the instruction named by a null-terminated string on the tape.
function h {
    local op c msg
    op=""
    for ((i=p; tape[i] != 0; i++)) do
        c=$(echo -e $(printf '\\x%x' "${tape[$i]}"))
        op="${op}${c}"
    done
    echo -e "\nHelp for '${op}':"
    op=$(echo "${op}" | sed -r 's/[.[*]/\\\0/g')
    grepPattern=" ${op}$"
    test $DEBUG && echo "grepPattern=${grepPattern}"
    grepResult=$(grep -T -n -A1 "${grepPattern}" $0)
    echo "${grepResult}"
    ip=$((ip + 1))
}

function :h {
    ip=$((ip + 1))
    echo "Interactive BF Interpreter"
    echo "This interpreter implements an extended brainfuck with modified syntax."
    echo ""
    echo "Control commands"
    echo "  :h      print this help message"
    echo "  :r      reset the interpreter"
    echo "  :q      quit/exit"
    echo ""
    echo "Syntax"
    echo "- instructions must be separated by spaces"
    echo "- control commands may be entered as if they're instructions"
    echo ""
    echo "Semantics"
    echo "- execution starts at the top of the tape"
    echo "- data and instruction pointers are never implicitly reset"
    echo "- brainfuck"
    echo ""
    echo "Instructions"
    echo "  ^       move data pointer up (\"left\") one cell"
    echo "  v       move data pointer down one cell"
    echo "  [       jump forward to matching ] if current cell is zero"
    echo "  ]       jump back to matching [ if current cell is not zero"
    echo "  +       increment cell"
    echo "  -       decrement cell"
    echo "  ,       read one byte"
    echo "  .       print one byte as char"
    echo "  *       debug print the tape"
    echo "  h       print help for instr named by null-terminated string at data pointer"
    echo ""
    echo "Note: If you've connected using netcat, you may wish to use"
    echo "Ctrl-D to send input for the , instruction. Otherwise, extra"
    echo "newlines will be sent and double-print the REPL prompt."
}

function :r {
    for ((i=0; i < 2048; i++)) do
        tape[i]=0;
    done
    ip=0
    p=0
    unset program
    declare -a program
}

function :q {
    exit 0
}

echo "Welcome! Use :h for help and :q to quit."

while true; do
    read -p "bf$ " -r -a prog 2>&1
    program+=(${prog[@]})

    if test $DEBUG ; then
        echo "ip=${ip}"
        echo "program=${program[@]}"
        echo "currentInstr=${program[$ip]}"
    fi
    cmd=${program[$ip]}
    while test ${cmd}; do
        validate "${cmd}"
        "${cmd}" 2>/dev/null || abort "${cmd}"
        cmd=${program[$ip]}
    done
done
