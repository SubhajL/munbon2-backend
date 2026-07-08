# sensor-data — IoT ingestion + chart APIs

**TypeScript / Express 4 + Socket.IO / Node 18** · Multiple entry points · **Extends [../../CLAUDE.md](../../CLAUDE.md)**

## Purpose
Ingests IoT telemetry (water-level, moisture): field sensors → AWS API Gateway/Lambda → **SQS** → local consumer → **TimescaleDB**, and serves it via REST/WebSocket/MQTT + chart-data APIs (some also deployed as AWS Lambdas).

## Commands
```bash
npm install
npm run dev            # nodemon ts-node src/cmd/server/main.ts (API, port 3001)
npm run consumer       # ts-node src/cmd/consumer/main.ts (SQS→Timescale, port 3004)
npm run build          # tsc
npm start              # node dist/cmd/server/main.js
npm test               # jest (ts-jest)
npm run lint           # eslint src/**/*.ts
npx tsc --noEmit       # typecheck (no dedicated script)
```

## Structure (`src/`)
- `cmd/server` (Express+Socket.IO+MQTT), `cmd/consumer` (SQS poller). `routes/` (`/api/v1`, `/api/v1/external`), `services/` (`sensor-data.service`, `sqs-processor`, `mqtt-broker`, chart-data services), `repository/` (`timescale.repository`, `dual-write.repository`), `transformers/`, `middleware/`, `utils/`.
- `lambda/handlers/*` + `deployments/aws-lambda/` (serverless ingestion), `deployments/k8s/`.

## Tests
Jest + ts-jest (`jest.config.js`); roots `src/`, `test/`, `lambda/`; `*.spec.ts`/`*.test.ts`, `supertest` for routes. Run `npm test`.

## Config / Ports / Env
- Ports: API **3001** (`PORT`), consumer **3004** (`CONSUMER_PORT`), unified-api 3000, MQTT 1883/8083.
- Stores: TimescaleDB/Postgres (primary), a config Postgres `munbon_dev`/`water_control_smartfarm`, MSSQL (SCADA, in `unified-api.js`), AWS SQS, in-process MQTT (mock), `ioredis`.
- Env: `TIMESCALE_HOST/PORT/DB/USER/PASSWORD`, `SQS_QUEUE_URL`, `AWS_*`, `ENABLE_DUAL_WRITE`, `EC2_DB_*`, `VALID_TOKENS`, `INTERNAL_API_KEY`, `ADMIN_TOKEN`.

## Integration
- Ingestion: `POST /api/v1/{token}/telemetry` (Lambda) → SQS → consumer → `TimescaleRepository`/`DualWriteRepository` (local + EC2) → emits `newData` over Socket.IO. Read APIs under `/api/v1`, Swagger at `/api-docs`, admin raw SQL at `/api/v1/admin/query`.

## Gotchas / Watch-outs
- ⚠️ **Committed secrets/hosts** (SEC): EC2 IP `43.208.201.191`, DB passwords, `INTERNAL_API_KEY` default `munbon-internal-…` in committed files → treat as compromised, rotate, do not extend the pattern.
- **Three PM2 ecosystem files** with different roles: `ecosystem.config.js` (local dev API+unified-api+cloudflare-tunnel), `ecosystem.consumer.config.js` (consumer, Timescale :5433 `munbon_timescale`), `ecosystem.ec2.config.js` (built consumer, :5432 `sensor_data`). **Inconsistent DB port/name defaults** across code (5432 vs 5433; `munbon_timescale` vs `sensor_data`).
- Consumer **deletes SQS messages even on processing failure** (prevents retries but can drop data).
- `tsconfig` is loose (`strict:false`, `noImplicitAny:false`). Heavy dead-code clutter: many `*.ts.skip/.bak/.backup`, `main-original.ts`, `unified-api-*` variants, ~150 root scripts — **verify a file is live before editing**.
- No Dockerfile / no service README; deployment is serverless (ingestion) + PM2/tunnel (APIs).
