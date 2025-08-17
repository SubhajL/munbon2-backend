# Cloud Deployment Options

## 1. AWS EC2 (Most Control)
```bash
# Use free tier t2.micro
# Deploy unified API to EC2
# Lambda can connect directly via VPC or public IP
```

## 2. AWS App Runner (Easiest)
```yaml
# apprunner.yaml
version: 1.0
runtime: nodejs18
build:
  commands:
    build:
      - npm install
run:
  runtime-version: latest
  command: node src/unified-api.js
  network:
    port: 3000
    env: PORT
  env:
    - name: TIMESCALE_HOST
      value: "your-rds-endpoint"
    - name: MSSQL_HOST
      value: "moonup.hopto.org"
```

## 3. Railway.app (Simple & Free Tier)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
```

## 4. Render.com (Free Tier)
- Auto-deploy from GitHub
- Environment variables support
- Free SSL
- Automatic restarts

## 5. AWS ECS Fargate (Serverless Containers)
```json
{
  "family": "unified-api",
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [{
    "name": "unified-api",
    "image": "your-ecr-repo/unified-api",
    "portMappings": [{
      "containerPort": 3000
    }]
  }]
}
```