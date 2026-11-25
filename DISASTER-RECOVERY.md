# Disaster Recovery — InfraOps Center

Guia de restauracao completa do InfraOps Center em caso de falha do hardware atual (Raspberry Pi) ou migracao para um servidor mais robusto.

---

## Importante: tempos diferentes de cada etapa

Este guia tem duas fases com tempos bem diferentes:

- **Fase 1 (preparar a maquina nova)**: manual, pode levar de 30 minutos a algumas horas, dependendo do hardware (instalar sistema operacional, configurar rede, instalar Docker).
- **Fase 2 (restaurar o InfraOps em si)**: rapida, geralmente 15 a 30 minutos, ja que todo o sistema roda em containers Docker prontos.

O Docker acelera MUITO a parte de "recriar a aplicacao", mas nao acelera a parte de "preparar um computador do zero".

---

## Pre-requisitos antes de precisar deste guia

- [ ] Arquivo .env salvo em local seguro (Bitwarden, nota segura)
- [ ] Backup do PostgreSQL rodando diariamente, replicado para dois servidores
- [ ] Acesso ao repositorio Git

---

## FASE 1 — Preparar a maquina nova (manual, mais lenta)

### 1.1. Instala o sistema operacional

Baixa e instala Ubuntu Server (ou distribuicao compativel) na maquina nova, via pendrive/instalador USB.

### 1.2. Instala o Docker

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER


---

## FASE 2 — Restaurar o InfraOps (rapida, via Docker)

### 2.1. Clona o repositorio

git clone https://github.com/Pedro-Amaral-008/Infraops-Center.git
cd Infraops-Center


### 2.2. Restaura o arquivo .env

Copia o conteudo salvo no Bitwarden para um novo arquivo .env na raiz do projeto.

### 2.3. Sobe os containers

cd docker/docker-compose
docker compose --env-file ../../.env up -d


### 2.4. Restaura o backup do banco de dados

Copia o backup mais recente (.sql.gz) de um dos servidores de destino e restaura.

### 2.5. Confirma o funcionamento

Acessa o painel web e testa login.

---

## Observacoes

Backup automatizado do PostgreSQL cobre dados relacionais (usuarios, auditoria, historico). O historico bruto de metricas do Prometheus nao esta incluido no backup.
