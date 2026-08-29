#!/bin/bash
set -e
DATA=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_DIR="/mnt/data/infraops/backups/postgres"
ARQUIVO="infraops_db_${DATA}.sql.gz"
CAMINHO_LOCAL="${BACKUP_DIR}/${ARQUIVO}"
API_URL="IP_INTERNO_AQUI:8000"
BACKUP_API_KEY="SUA_API_KEY_AQUI"
STATUS="Success"

echo "=== Iniciando backup do PostgreSQL - ${DATA} ==="
docker exec infraops_postgres pg_dump -U infraops_admin infraops_db | gzip > "$CAMINHO_LOCAL"

if [ -s "$CAMINHO_LOCAL" ]; then
    TAMANHO_BYTES=$(stat -c%s "$CAMINHO_LOCAL")
    echo "Backup local criado com sucesso: $CAMINHO_LOCAL ($(du -h "$CAMINHO_LOCAL" | cut -f1))"
else
    echo "ERRO: backup local vazio ou nao criado"
    STATUS="Failed"
    TAMANHO_BYTES=0
fi

echo "Enviando para servidor principal (IP_SRV_BACKUP)..."
if scp -o StrictHostKeyChecking=no "$CAMINHO_LOCAL" "Administrador@IP_SRV_BACKUP:/A:/Backups/Bkp infraOps/"; then
    echo "OK: enviado para principal"
else
    echo "ERRO: falha ao enviar para principal"
    STATUS="Failed"
fi

echo "Removendo backups locais com mais de 30 dias..."
find "$BACKUP_DIR" -name "infraops_db_*.sql.gz" -mtime +30 -delete

echo "Reportando status ao InfraOps..."
curl -s -X POST "${API_URL}/backups/registrar" \
  -H "x-api-key: ${BACKUP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"job_name\":\"Backup E-Ops\",\"instance\":\"eops\",\"backup_type\":\"Dump PostgreSQL\",\"status\":\"${STATUS}\",\"tamanho_transferido_bytes\":${TAMANHO_BYTES},\"executado_em\":\"$(date -u +%Y-%m-%dT%H:%M:%S)\"}"

echo "=== Backup finalizado ==="
