#!/bin/bash
# HTTPS autofirmado para demo Prevex (micrófono / secure context).
set -euo pipefail

CERT_DIR=/home/ec2-user/prevex/certs
PFX="$CERT_DIR/prevex.pfx"
CRT="$CERT_DIR/prevex.crt"
KEY="$CERT_DIR/prevex.key"
PASS='REDACTED'
IP='0.0.0.0'
ENV_FILE=/home/ec2-user/prevex/prevex.env

sudo mkdir -p "$CERT_DIR"

if [[ ! -f "$PFX" ]]; then
  echo "Generando certificado autofirmado para $IP ..."
  sudo openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$KEY" \
    -out "$CRT" \
    -days 825 \
    -subj "/CN=$IP/O=Prevex Demo/C=AR" \
    -addext "subjectAltName=IP:$IP,DNS:localhost"
  sudo openssl pkcs12 -export \
    -out "$PFX" \
    -inkey "$KEY" \
    -in "$CRT" \
    -passout "pass:$PASS"
  sudo chmod 600 "$PFX" "$KEY"
  sudo chmod 644 "$CRT"
  sudo chown root:root "$PFX" "$KEY" "$CRT"
fi

# Actualizar env: HTTPS + cert + PublicBaseUrl
TMP=$(mktemp)
sudo grep -vE '^(ASPNETCORE_URLS|App__PublicBaseUrl|Kestrel__Certificates__Default__Path|Kestrel__Certificates__Default__Password)=' "$ENV_FILE" > "$TMP" || true
{
  cat "$TMP"
  echo "ASPNETCORE_URLS=https://0.0.0.0:443;http://0.0.0.0:80"
  echo "App__PublicBaseUrl=https://$IP"
  echo "Kestrel__Certificates__Default__Path=$PFX"
  echo "Kestrel__Certificates__Default__Password=$PASS"
} | sudo tee "$ENV_FILE" >/dev/null
rm -f "$TMP"
sudo chmod 600 "$ENV_FILE"
sudo chown root:root "$ENV_FILE"

echo "=== prevex.env keys ==="
sudo grep -E '^[A-Za-z0-9_]+=' "$ENV_FILE" | cut -d= -f1

sudo systemctl daemon-reload
sudo systemctl restart prevex
sleep 3
sudo systemctl is-active prevex
sudo ss -tlnp | grep -E ':80|:443' || true
curl -sk -o /dev/null -w "https:%{http_code}\n" "https://127.0.0.1/" || true
curl -s -o /dev/null -w "http:%{http_code}\n" "http://127.0.0.1/" || true

echo "OK: abrí https://$IP (aceptá el aviso del certificado autofirmado)."
echo "Si no carga: agregá regla TCP 443 en el Security Group del EC2."
