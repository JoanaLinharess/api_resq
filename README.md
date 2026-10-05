# Data Lake Metadata Catalog

API REST para catálogo de metadados de tabelas de um Data Lake.

## Objetivo

Registrar, consultar, atualizar e remover metadados de tabelas (identidade, dono, domínio, colunas e evolução simples de schema), com validações de qualidade de dados.

## Arquitetura

```text
API (FastAPI) → Service → Repository → MongoDB
                 ↑
              Domain model
```

- **API/Router**: HTTP, status codes e serialização.
- **Service**: regras de negócio (unicidade da tabela e orquestração).
- **Repository**: persistência MongoDB.
- **Domain model**: entidade `Metadata` e incremento de `schema_version`.
- **Schemas Pydantic**: contrato e validação de entrada/saída.

## Tecnologias

- Python 3.12
- FastAPI
- Pydantic v2
- Motor / MongoDB
- Pytest
- Docker Compose

## Pré-requisitos

- Python 3.12+
- Docker e Docker Compose (para o MongoDB ou para subir a stack completa)

## Configuração do `.env`

```bash
cp .env.example .env
```

| Variável       | Descrição                         | Exemplo                         |
|----------------|-----------------------------------|---------------------------------|
| `MONGODB_URI`  | URI de conexão do MongoDB         | `mongodb://localhost:27017`     |
| `MONGODB_DB`   | Nome do banco                     | `data_lake_catalog`             |

Não commitar o arquivo `.env`.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Como executar

### Opção 1 — API local + MongoDB no Docker

```bash
docker compose up -d mongo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Opção 2 — stack completa

```bash
docker compose up --build
```

A API fica em `http://localhost:8000`.

## Como executar os testes

```bash
pytest
```

Os testes unitários e de API usam um repositório em memória e não exigem MongoDB.

Os testes marcados com `mongo` sobem contra um MongoDB real, em um banco isolado (`data_lake_catalog_test`). Sem Mongo no ar, esses casos são ignorados (`skipped`).

```bash
docker compose up -d mongo
pytest -m mongo
```

Para falhar se o MongoDB não estiver disponível:

```bash
MONGODB_REQUIRED=1 pytest -m mongo
```

## Documentação da API

Com a aplicação no ar:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Endpoints

| Método   | Caminho                 | Descrição                          |
|----------|-------------------------|------------------------------------|
| `GET`    | `/health`               | Saúde da API e do MongoDB          |
| `POST`   | `/metadata`             | Cria metadado                      |
| `GET`    | `/metadata`             | Lista com filtros e paginação      |
| `GET`    | `/metadata/{id}`        | Busca por ID                       |
| `GET`    | `/metadata/{id}/history`| Evolução do schema da tabela       |
| `PUT`    | `/metadata/{id}`        | Atualiza metadado                  |
| `DELETE` | `/metadata/{id}`        | Remove metadado                    |

Query params da listagem: `table_name` (busca parcial), `owner`, `domain`, `page`, `page_size`.

Status codes: `201`, `200`, `204`, `400` (ID inválido), `404`, `409` (tabela duplicada), `422` (payload inválido), `503` (falha de banco).

## Exemplos de requests

### Criar

```bash
curl -X POST http://localhost:8000/metadata \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "orders",
    "description": "Customer orders",
    "database": "sales",
    "schema": "public",
    "owner": "data-eng",
    "domain": "commerce",
    "columns": [
      {
        "name": "order_id",
        "type": "string",
        "description": "Order identifier",
        "nullable": false
      },
      {
        "name": "amount",
        "type": "decimal",
        "description": "Order amount",
        "nullable": true
      }
    ]
  }'
```

### Listar

```bash
curl "http://localhost:8000/metadata?table_name=ord&owner=data-eng&page=1&page_size=20"
```

### Buscar por ID

```bash
curl http://localhost:8000/metadata/<metadata_id>
```

### Atualizar

```bash
curl -X PUT http://localhost:8000/metadata/<metadata_id> \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "orders",
    "description": "Updated description",
    "database": "sales",
    "schema": "public",
    "owner": "data-eng",
    "domain": "commerce",
    "columns": [
      {
        "name": "order_id",
        "type": "bigint",
        "description": "Order identifier",
        "nullable": false
      }
    ]
  }'
```

### Histórico de schema

```bash
curl http://localhost:8000/metadata/<metadata_id>/history
```

### Remover

```bash
curl -X DELETE http://localhost:8000/metadata/<metadata_id>
```

## Decisões arquiteturais

- **Repository + Service**: separa HTTP, regra de negócio e persistência, e permite testar o service sem MongoDB.
- **Identidade da tabela**: `database + schema + table_name` é única. Conflito retorna `409`.
- **Evolução de schema**: `schema_version` começa em `1` e sobe quando mudam nome, tipo ou nullability das colunas. Cada versão é gravada em `metadata_history` e consultada em `GET /metadata/{id}/history`. Mudança só de descrição/owner não gera versão nova.
- **Qualidade de metadados**: strings obrigatórias não podem ser vazias; nomes de coluna são únicos (case-insensitive).
- **Índices MongoDB**: único na identidade da tabela; `table_name`, `owner`, `domain` e `created_at` para listagem.
- **IDs**: `ObjectId` do MongoDB, exposto como string. ID malformado retorna `400`.
- **PUT**: substituição completa dos campos editáveis.
- **Docker Compose**: sobe MongoDB (e opcionalmente a API) sem autenticação local, para reduzir fricção no case.
