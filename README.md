# Energy Bill AI Backend

Backend profissional em Python para ingestao inteligente de contas de energia, extracao estruturada, revisao humana, analytics de consumo, previsao dos proximos meses e geracao de insights.

## Status Atual

O projeto entrega, neste momento:

- autenticacao JWT com cadastro, login e rota `me`
- refresh tokens com rotacao e logout server-side
- upload autenticado de PDF, JPG, JPEG e PNG
- armazenamento do documento original e metadados
- extracao de texto com `pdfplumber`
- OCR com `pytesseract` e `pypdfium2`
- parser semantico heuristico com confidence por campo
- validacao de regras de negocio
- revisao humana obrigatoria antes da confirmacao
- rate limiting configuravel nas rotas sensiveis
- analytics e forecasting apenas para contas confirmadas
- previsao com `Prophet` ou fallback deterministico
- insights persistidos
- seed de desenvolvimento com cenarios confirmados e pendentes de revisao
- workflow de CI com compile, migration, tests e build Docker
- pipeline de release para GHCR e deploy remoto via SSH

## Arquitetura

```mermaid
flowchart LR
    A["Cliente REST"] --> B["FastAPI Routers"]
    B --> C["Auth Dependency"]
    B --> D["Application Services"]
    D --> E["Repositories"]
    E --> F["PostgreSQL"]
    D --> G["Document Pipeline"]
    G --> H["pdfplumber / OCR"]
    G --> I["Normalizer + Semantic Parser"]
    G --> J["Validator + Confidence Engine"]
    D --> K["Analytics + Forecast"]
    D --> L["Local Storage"]
```

## Regras Operacionais Importantes

- Rotas de negocio exigem autenticacao Bearer.
- O upload agora usa o usuario autenticado, nao um `user_id` enviado pelo cliente.
- Tokens de refresh sao rotacionados a cada renovacao.
- O backend aplica rate limiting em login, refresh, upload e extracao.
- Analytics e forecast retornam `409` para contas ainda nao confirmadas.
- Campos de baixa confianca nunca sao aceitos silenciosamente.
- O metodo de forecast sempre e retornado ao cliente.

## Stack Tecnica

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- Alembic
- Pydantic v2
- Pandas
- Numpy
- pdfplumber
- Pillow
- pytesseract
- pypdfium2
- Prophet
- PyJWT
- pwdlib + Argon2
- Docker e docker-compose

## Estrutura de Pastas

```text
app/
  api/
  core/
  db/
  models/
  repositories/
  schemas/
  services/
    analytics/
    auth/
    documents/
    extraction/
    forecasting/
    review/
  utils/
alembic/
docker/
scripts/
tests/
  integration/
  unit/
uploads/
.github/workflows/
```

## Variaveis de Ambiente

| Variavel | Default | Descricao |
| --- | --- | --- |
| `APP_NAME` | `Energy Bill AI Backend` | Nome da aplicacao |
| `APP_VERSION` | `0.1.0` | Versao atual |
| `ENVIRONMENT` | `development` | Ambiente em execucao |
| `DEBUG` | `false` | Modo debug do FastAPI |
| `API_V1_PREFIX` | `/api/v1` | Prefixo da API versionada |
| `DATABASE_URL` | `postgresql+psycopg://energy_user:energy_pass@localhost:5432/energy_bill_ai` | URL do banco |
| `UPLOADS_DIR` | `uploads` | Diretorio base de armazenamento |
| `LOG_LEVEL` | `INFO` | Nivel de log |
| `DB_POOL_SIZE` | `10` | Tamanho do pool |
| `DB_MAX_OVERFLOW` | `20` | Overflow do pool |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | Timeout do pool |
| `DB_POOL_RECYCLE_SECONDS` | `1800` | Reciclagem do pool |
| `MAX_UPLOAD_SIZE_MB` | `15` | Limite maximo do upload |
| `LOW_CONFIDENCE_THRESHOLD` | `0.75` | Limiar para revisao manual |
| `OCR_LANGUAGES` | `por+eng` | Idiomas do OCR |
| `TESSERACT_CMD` | vazio | Caminho do binario Tesseract |
| `JWT_SECRET_KEY` | `change-this-in-production` | Chave de assinatura JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Expiracao do token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Expiracao do refresh token |
| `RATE_LIMIT_ENABLED` | `true` | Habilita rate limiting |
| `AUTH_RATE_LIMIT_REQUESTS` | `5` | Limite das rotas de auth |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `60` | Janela das rotas de auth |
| `UPLOAD_RATE_LIMIT_REQUESTS` | `10` | Limite da rota de upload |
| `UPLOAD_RATE_LIMIT_WINDOW_SECONDS` | `300` | Janela da rota de upload |
| `EXTRACTION_RATE_LIMIT_REQUESTS` | `10` | Limite da rota de extracao |
| `EXTRACTION_RATE_LIMIT_WINDOW_SECONDS` | `300` | Janela da rota de extracao |
| `FORECAST_HORIZON_MONTHS` | `8` | Horizonte de previsao |
| `PROPHET_MIN_HISTORY_POINTS` | `12` | Minimo para usar Prophet |
| `FORECAST_INTERVAL_ZSCORE` | `1.96` | Largura dos intervalos do fallback |
| `ENABLE_PROPHET` | `true` | Habilita uso de Prophet |

## Como Rodar Localmente

### 1. Copie o ambiente

```bash
cp .env.example .env
```

### 2. Instale dependencias

```bash
pip install -r requirements.txt
```

### 3. Suba o banco

```bash
docker compose up -d db
```

### 4. Rode as migrations

```bash
python -m alembic -c alembic.ini upgrade head
```

### 5. Inicie a API

```bash
uvicorn app.main:app --reload
```

### 6. Acesse a documentacao interativa

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Healthcheck: [http://localhost:8000/health](http://localhost:8000/health)

## Como Rodar Com Docker Compose

```bash
cp .env.example .env
docker compose up -d db
docker compose run --rm api python -m alembic -c alembic.ini upgrade head
docker compose up --build api
```

O `docker-compose.yml` faz override do `DATABASE_URL` da API para usar o host interno `db`. O `.env.example` fica preparado para execucao local no host.

## Seed de Desenvolvimento

Para criar um usuario autenticavel, uma carteira historica confirmada e um cenario pendente de revisao:

```bash
python scripts/seed_dev_data.py
```

Parametros opcionais:

```bash
python scripts/seed_dev_data.py --name "Seed User" --email seed.user@example.com --password ChangeMe123!
```

Esse script:

- cria ou atualiza o usuario principal
- cria 13 contas confirmadas e gera analytics/forecast
- cria 1 conta adicional em `PENDING_REVIEW` com confidence e extraction logs
- opcionalmente cria um segundo usuario com carteira reduzida para testes multi-tenant
- cria documentos placeholder em PDF para todos os cenarios

## Endpoints

### Publicos

| Metodo | Rota | Finalidade |
| --- | --- | --- |
| `GET` | `/health` | Healthcheck da aplicacao e do banco |
| `POST` | `/api/v1/auth/register` | Cadastro de usuario |
| `POST` | `/api/v1/auth/login` | Login e emissao do token |
| `POST` | `/api/v1/auth/refresh` | Rotacao do refresh token |
| `POST` | `/api/v1/auth/logout` | Revogacao do refresh token |

### Protegidos por Bearer Token

| Metodo | Rota | Finalidade |
| --- | --- | --- |
| `GET` | `/api/v1/auth/me` | Usuario autenticado |
| `POST` | `/api/v1/documents/upload` | Upload do documento |
| `POST` | `/api/v1/bills/extract` | Extracao da conta |
| `GET` | `/api/v1/bills/{bill_id}` | Payload de revisao |
| `POST` | `/api/v1/bills/{bill_id}/confirm` | Confirmacao manual |
| `GET` | `/api/v1/bills/{bill_id}/analytics` | Analytics da conta |
| `GET` | `/api/v1/bills/{bill_id}/forecast` | Forecast da conta |
| `GET` | `/api/v1/users/{user_id}/history` | Historico do usuario autenticado |

## Fluxo de Uso

1. Cadastre ou autentique um usuario.
2. Guarde `access_token` e `refresh_token`.
3. Envie o documento em `/api/v1/documents/upload`.
4. Extraia a conta em `/api/v1/bills/extract`.
5. Revise os campos retornados.
6. Confirme a conta em `/api/v1/bills/{bill_id}/confirm`.
7. Use `/api/v1/auth/refresh` quando o access token expirar.
8. Consulte analytics e forecast.

## Exemplos de API

### 1. Registro

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo User",
    "email": "demo@example.com",
    "password": "StrongPass123!"
  }'
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "StrongPass123!"
  }'
```

Resposta resumida:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_seconds": 3600,
  "refresh_expires_in_seconds": 1209600,
  "user": {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Demo User",
    "email": "demo@example.com",
    "created_at": "2026-04-09T12:00:00Z"
  }
}
```

### 3. Refresh do token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<REFRESH_TOKEN>"
  }'
```

### 4. Upload autenticado

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -F "file=@./samples/conta.pdf;type=application/pdf"
```

### 5. Extracao

```bash
curl -X POST "http://localhost:8000/api/v1/bills/extract" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "c4f8d78a-75e0-4977-93c8-8d9c8f7c4e1f"
  }'
```

### 6. Confirmacao

```bash
curl -X POST "http://localhost:8000/api/v1/bills/<BILL_ID>/confirm" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "concessionaria": "Enel Sao Paulo",
      "mes_referencia": "2026-04",
      "consumo_kwh": "252.000",
      "dias_faturados": 29,
      "valor_total": "198.45",
      "bandeira_tarifaria": "Verde",
      "unidade_consumidora": "123456789",
      "vencimento": "2026-05-15",
      "historico_consumo": [
        {"mes_referencia": "2025-12", "consumo_kwh": "301.000", "dias_faturados": 33},
        {"mes_referencia": "2026-01", "consumo_kwh": "336.000", "dias_faturados": 29},
        {"mes_referencia": "2026-02", "consumo_kwh": "267.000", "dias_faturados": 28},
        {"mes_referencia": "2026-03", "consumo_kwh": "336.000", "dias_faturados": 32},
        {"mes_referencia": "2026-04", "consumo_kwh": "252.000", "dias_faturados": 29}
      ]
    }
  }'
```

### 7. Analytics

```bash
curl "http://localhost:8000/api/v1/bills/<BILL_ID>/analytics" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 8. Forecast

```bash
curl "http://localhost:8000/api/v1/bills/<BILL_ID>/forecast" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Contrato de Erro

```json
{
  "error": {
    "code": "not_authenticated",
    "message": "Authentication credentials were not provided.",
    "details": null,
    "request_id": "53a8e659-450f-4027-a89a-8cc9db23970f"
  }
}
```

Codigos relevantes ja cobertos por testes:

- `not_authenticated`
- `invalid_credentials`
- `refresh_token_reused`
- `refresh_token_revoked`
- `forbidden`
- `rate_limit_exceeded`
- `unsupported_file_type`
- `document_not_found`
- `bill_not_found`
- `bill_not_confirmed`
- `request_validation_error`

## Testes

Rodar tudo:

```bash
pytest -q
```

Rodar unitarios:

```bash
pytest tests/unit -q
```

Rodar integracao:

```bash
pytest tests/integration -q
```

## CI

O projeto inclui workflow em [.github/workflows/ci.yml](./.github/workflows/ci.yml) com:

- instalacao de dependencias
- `compileall`
- `alembic upgrade head` em PostgreSQL
- `pytest -q`
- `docker build`

Tambem inclui workflow em [.github/workflows/release.yml](./.github/workflows/release.yml) para:

- publicar imagem em `ghcr.io`
- versionar por `sha`, `latest` e tags `v*`
- acionar deploy remoto opcional via SSH

## Deploy

### Render

O deploy no Render deve usar PostgreSQL gerenciado do proprio Render. Nao use a URL do Docker Compose (`@db:5432`), `localhost` ou `127.0.0.1` no `DATABASE_URL`, porque esses hosts existem apenas localmente e causam erro de DNS como `psycopg.OperationalError: Name or service not known`.

Opcao recomendada:

1. criar o deploy por Blueprint usando [render.yaml](./render.yaml)
2. deixar o `DATABASE_URL` vir de `fromDatabase`
3. manter `ENVIRONMENT=production`
4. manter `JWT_SECRET_KEY` gerado como segredo

Se o servico ja existe manualmente no Render, ajuste em **Environment**:

```bash
DATABASE_URL=<Internal Database URL do PostgreSQL no Render>
ENVIRONMENT=production
JWT_SECRET_KEY=<segredo forte>
SMS_PROVIDER=mock
```

O comando de start esperado e:

```bash
python -m alembic -c alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Arquivos relevantes:

- [docker-compose.prod.yml](./docker-compose.prod.yml)
- [docker/Dockerfile](./docker/Dockerfile)
- [scripts/deploy.sh](./scripts/deploy.sh)

Fluxo recomendado:

1. manter `.env` de producao no servidor
2. exportar `APP_IMAGE=ghcr.io/<owner>/energy-bill-ai-backend:sha-<commit>`
3. executar `bash ./scripts/deploy.sh`

O script faz `pull` da imagem, sobe o banco, roda `alembic upgrade head` e reinicia a API.

## Validacoes Ja Executadas

No estado atual do projeto, ja foram validados localmente:

- `pytest -q`
- `python -m compileall app tests scripts`
- `configure_mappers()`
- `alembic upgrade head`

## Limitacoes Atuais

- parser semantico ainda e heuristico
- OCR depende do binario do Tesseract no ambiente
- rate limiting atual e em memoria e por instancia
- nao ha fila assincrona para processamento pesado
- storage ainda e local em filesystem
- analytics e forecast persistidos ainda dependem da conta confirmada no fluxo online

## Melhorias Futuras Recomendadas

- backend distribuido para rate limiting
- S3 ou storage compativel
- processamento assincrono com fila
- parsers dedicados por concessionaria
- observabilidade com Prometheus e tracing
- auditoria de seguranca mais aprofundada

## AGENTS.md

O repositorio inclui [AGENTS.md](./AGENTS.md) com as regras de engenharia usadas neste backend.
