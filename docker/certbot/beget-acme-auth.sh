#!/bin/sh
# certbot --manual-auth-hook: publish the ACME TXT record through the Beget
# DNS API and wait until Beget's authoritative servers answer with it.
# Credentials: /root/.beget-api with BEGET_LOGIN and BEGET_PASSWORD (mode 600).
set -eu
. /root/.beget-api
fqdn="_acme-challenge.$CERTBOT_DOMAIN"

input=$(python3 -c 'import json, sys, urllib.parse
print(urllib.parse.quote(json.dumps({"fqdn": sys.argv[1], "records": {"TXT": [{"priority": 10, "value": sys.argv[2]}]}})))' "$fqdn" "$CERTBOT_VALIDATION")
answer=$(curl -s --max-time 30 "https://api.beget.com/api/dns/changeRecords?login=$BEGET_LOGIN&passwd=$BEGET_PASSWORD&input_format=json&output_format=json&input_data=$input")
case "$answer" in
  *'"result":true'*) ;;
  *) echo "beget changeRecords failed for $fqdn: $answer" >&2; exit 1 ;;
esac

# The zone is served by four nameservers that sync at different moments and
# Let's Encrypt may ask any of them: wait for every one, then a little more.
i=0
while [ $i -lt 40 ]; do
  ok=1
  for ns in ns1.beget.ru ns2.beget.com ns1.beget.pro ns2.beget.pro; do
    dig +short +time=5 TXT "$fqdn" "@$ns" | grep -q "$CERTBOT_VALIDATION" || ok=0
  done
  if [ $ok -eq 1 ]; then
    sleep 60
    exit 0
  fi
  i=$((i + 1)); sleep 15
done
echo "TXT for $fqdn is not visible on all Beget nameservers after 10 minutes" >&2
exit 1
