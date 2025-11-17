# Sensor Data Frontend + API Deployment

## Frontend (S3 + CloudFront)

- Prereqs: AWS CLI v2.
- Create and deploy:

```
./scripts/deploy-frontend-s3-cloudfront.sh \
  --bucket <unique-bucket-name> \
  --region ap-southeast-1
```

- Output prints the CloudFront domain. Open `https://<domain>/index.html` and set the API base.

## Backend (Lambda + API Gateway HTTP API)

- Prereqs: AWS CLI v2, SAM CLI.
- VPC: choose private subnets and a security group that can reach the TimescaleDB SG on 5432.
- Deploy:

```
./scripts/deploy-sensor-data-api.sh \
  --stack sensor-data-api \
  --region ap-southeast-1 \
  --subnets subnet-aaa,subnet-bbb \
  --sg sg-xxxx \
  --db-host <db-private-ip> \
  --db-user postgres \
  --db-pass '***' \
  --db-name sensor_data \
  --stage prod \
  --cors-origin https://<your-cloudfront-domain>
```

- Output prints the API base. Use it with the frontend via `?api=<api-base>/api/v1` or save it in index.html.

## Service .env

Copy `services/sensor-data/.env.example` and fill in all fields (do not commit `.env`).

