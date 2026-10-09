#!/usr/bin/env bash
set -euo pipefail
cd /opt/socialchef/backend

# Remove leftover default-compose stack that published DB/Redis.
docker ps -aq --filter name=fastapi-template | xargs -r docker rm -f
docker network rm fastapi-template_default 2>/dev/null || true

# Rotate secrets.
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SUPERUSER_PASSWORD=$(openssl rand -base64 18 | tr -d '=+/' | cut -c1-20)
SSO_SECRET=$(openssl rand -hex 24)

python3 - "$SECRET_KEY" "$POSTGRES_PASSWORD" "$SUPERUSER_PASSWORD" "$SSO_SECRET" <<'PY'
from pathlib import Path
import re
import sys

secret_key, pg_pw, su_pw, sso = sys.argv[1:5]
p = Path(".env")
text = p.read_text()
repls = {
    "SECRET_KEY": secret_key,
    "POSTGRES_PASSWORD": pg_pw,
    "FIRST_SUPERUSER_PASSWORD": su_pw,
    "SSO_SECRET_KEY": sso,
    "FIRST_SUPERUSER": "admin@example.com",
    "EMAILS_FROM_EMAIL": "noreply@example.com",
}
for key, value in repls.items():
    text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)
p.write_text(text)
Path("/root/socialchef-admin.txt").write_text(
    "FIRST_SUPERUSER=admin@example.com\n"
    f"FIRST_SUPERUSER_PASSWORD={su_pw}\n"
)
print("secrets rotated")
PY

# Publish API on host:8000; rely on ufw to block public access to 8000.
sed -i 's/"127.0.0.1:8000:8000"/"8000:8000"/' docker-compose.prod.yml

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable >/dev/null

export DOCKER_BUILDKIT=1
docker compose -f docker-compose.prod.yml --env-file .env down
docker compose -f docker-compose.prod.yml --env-file .env up -d --force-recreate

for i in $(seq 1 48); do
  status=$(docker inspect --format='{{.State.Health.Status}}' backend-backend-1 2>/dev/null || echo missing)
  echo "attempt $i health=$status"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  if [[ "$status" == "unhealthy" ]]; then
    docker compose -f docker-compose.prod.yml logs backend --tail 80
    exit 1
  fi
  sleep 5
done

ss -lntp | grep -E ':80 |:8000 |:5432 |:6379 ' || true
curl -s -o /dev/null -w 'local_docs:%{http_code}\n' http://127.0.0.1:8000/docs
curl -s -o /dev/null -w 'local_openapi:%{http_code}\n' http://127.0.0.1:8000/api/v1/openapi.json
docker compose -f docker-compose.prod.yml ps
echo REDEPLOY_OK
