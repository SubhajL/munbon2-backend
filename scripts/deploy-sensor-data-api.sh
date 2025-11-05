#!/usr/bin/env bash
set -euo pipefail

# Deploy Sensor Data API via AWS SAM
# Requirements: AWS CLI v2, AWS SAM CLI, Node.js 20, esbuild (SAM can auto-install), jq

usage() {
  cat <<USAGE
Usage: $0 \
  --stack <stack-name> \
  --region <region> \
  --subnets <subnet-ids-comma> \
  --sg <security-group-ids-comma> \
  --db-host <private-ip-or-host> \
  --db-user <user> \
  --db-pass <password> \
  [--db-name sensor_data] [--stage prod] [--cors-origin https://example.cloudfront.net]
USAGE
}

STACK="sensor-data-api"
REGION="ap-southeast-1"
SUBNETS=""
SGS=""
DB_HOST=""
DB_USER="postgres"
DB_PASS=""
DB_NAME="sensor_data"
STAGE="prod"
CORS_ORIGIN="*"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack) STACK="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    --subnets) SUBNETS="$2"; shift 2;;
    --sg) SGS="$2"; shift 2;;
    --db-host) DB_HOST="$2"; shift 2;;
    --db-user) DB_USER="$2"; shift 2;;
    --db-pass) DB_PASS="$2"; shift 2;;
    --db-name) DB_NAME="$2"; shift 2;;
    --stage) STAGE="$2"; shift 2;;
    --cors-origin) CORS_ORIGIN="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$SUBNETS" || -z "$SGS" || -z "$DB_HOST" || -z "$DB_PASS" ]]; then
  echo "Missing required parameters"; usage; exit 1
fi

TEMPLATE="infra/sensor-data-api/template.yaml"

sam build -t "$TEMPLATE" --region "$REGION"

sam deploy \
  --stack-name "$STACK" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    StackName=$STACK \
    StageName=$STAGE \
    RegionParam=$REGION \
    SubnetIds=$(echo "$SUBNETS" | tr ',' ' ') \
    SecurityGroupIds=$(echo "$SGS" | tr ',' ' ') \
    TimescaleHost=$DB_HOST \
    TimescalePort=5432 \
    TimescaleDb=$DB_NAME \
    TimescaleUser=$DB_USER \
    TimescalePassword=$DB_PASS \
    CorsAllowedOrigin=$CORS_ORIGIN

API_URL=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)

echo "\n✅ Deployed. API base: $API_URL"
echo "Moisture: $API_URL/api/v1/moisture/chart?period=24h"
echo "Water levels: $API_URL/api/v1/water-levels/chart?period=24h"

