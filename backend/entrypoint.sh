#!/bin/sh
# Sobe o banco na versão mais nova, faz a carga inicial se estiver vazio e inicia a API.
# O container começa como root só para acertar o dono de ./data e ./secrets; depois a API
# roda como o usuário "app" (sem privilégio).
set -e

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data /app/secrets
  # Em pastas do Windows (Docker Desktop) o chown pode não valer; aí basta a pasta aceitar escrita
  chown -R app:app /app/data /app/secrets 2>/dev/null || true
  if setpriv --reuid=app --regid=app --init-groups sh -c 'test -w /app/data && test -w /app/secrets'; then
    exec setpriv --reuid=app --regid=app --init-groups "$0" "$@"
  fi
  echo "AVISO: o usuário app não consegue gravar em ./data ou ./secrets; seguindo como root." >&2
fi

cd /app/backend
alembic upgrade head
python -m app.seed
# 0.0.0.0 é o endereço dentro do container; no navegador o endereço é localhost
echo "Painel no ar: abra http://localhost:8000 no navegador (o 0.0.0.0 abaixo é interno do Docker)."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
