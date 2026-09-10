#!/bin/sh
# certbot --manual-cleanup-hook: drop the ACME TXT record set again.
set -eu
. /root/.beget-api
fqdn="_acme-challenge.$CERTBOT_DOMAIN"
input=$(python3 -c 'import json, sys, urllib.parse
print(urllib.parse.quote(json.dumps({"fqdn": sys.argv[1], "records": {}})))' "$fqdn")
curl -s --max-time 30 "https://api.beget.com/api/dns/changeRecords?login=$BEGET_LOGIN&passwd=$BEGET_PASSWORD&input_format=json&output_format=json&input_data=$input" >/dev/null || true
