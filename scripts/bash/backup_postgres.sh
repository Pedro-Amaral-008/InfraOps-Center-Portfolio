#!/bin/bash
set -e

DATA=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_DIR="/mnt/data/infraops/backups/postgres"
ARQUIVO="infraops_db_${DATA}.sql.gz"
CAMINHO_LOCAL="${BACKUP_DIR}/${ARQUIVO}"

echo "=== Iniciando backup do PostgreSQL - ${DATA} ==="

docker exec infraops_postgres pg_dump -U infraops_admin infraops_db | gzip > "$CAMINHO_LOCAL"

if [ -s "$CAMINHO_LOCAL" ]; then
    echo "Backup local criado com sucesso: $CAMINHO_LOCAL ($(du -h "$CAMINHO_LOCAL" | cut -f1))"
else
    echo "ERRO: backup local vazio ou nao criado"
    exit 1
fi

echo "Enviando para servidor principal (IP_INTERNO_AQUI)..."
scp -o StrictHostKeyChecking=no "$CAMINHO_LOCAL" "Administrador@IP_INTERNO_AQUI:/A:/Backups/Bkp infraOps/" && echo "OK: enviado para principal" || echo "ERRO: falha ao enviar para principal"

echo "Enviando para servidor redundante (IP_INTERNO_AQUI)..."
scp -o StrictHostKeyChecking=no "$CAMINHO_LOCAL" "Administrator@IP_INTERNO_AQUI:/E:/Backup Matriz/Bkp infraOps/" && echo "OK: enviado para redundante" || echo "ERRO: falha ao enviar para redundante"

echo "Removendo backups locais com mais de 30 dias..."
find "$BACKUP_DIR" -name "infraops_db_*.sql.gz" -mtime +30 -delete

echo "=== Backup finalizado ==="
