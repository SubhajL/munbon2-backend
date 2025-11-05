#!/usr/bin/env bash
set -euo pipefail

# Deploy static frontend to S3 + CloudFront (OAC)
# Requirements: AWS CLI v2, jq

usage() {
  cat <<USAGE
Usage: $0 --bucket <bucket-name> --region <region> [--cf-alias <optional-domain>]
USAGE
}

BUCKET=""
REGION="ap-southeast-1"
CF_ALIAS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    --cf-alias) CF_ALIAS="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg $1"; usage; exit 1;;
  esac
done

if [[ -z "$BUCKET" ]]; then echo "--bucket required"; usage; exit 1; fi

# Create bucket if missing
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION"
fi

# Create OAC
OAC_ID=$(aws cloudfront create-origin-access-control \
  --origin-access-control-config '{"Name":"'"$BUCKET"' OAC","Description":"OAC for '"$BUCKET"'","SigningProtocol":"sigv4","SigningBehavior":"always","OriginAccessControlOriginType":"s3"}' \
  --query 'OriginAccessControl.Id' --output text)

# Create CloudFront distribution
DIST_CONFIG=$(mktemp)
cat > "$DIST_CONFIG" <<JSON
{
  "CallerReference": "$(date +%s)",
  "Comment": "Munbon Frontend",
  "Enabled": true,
  "Origins": {
    "Items": [
      {
        "Id": "s3-$BUCKET",
        "DomainName": "$BUCKET.s3.$REGION.amazonaws.com",
        "S3OriginConfig": { "OriginAccessIdentity": "" },
        "OriginAccessControlId": "$OAC_ID"
      }
    ],
    "Quantity": 1
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-$BUCKET",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
    "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
    "Compress": true,
    "ForwardedValues": {"QueryString": true, "Cookies": {"Forward": "none"}}
  },
  "DefaultRootObject": "index.html"
}
JSON

DIST_ID=$(aws cloudfront create-distribution --distribution-config file://"$DIST_CONFIG" \
  --query 'Distribution.Id' --output text)

DIST_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)

# Attach bucket policy for OAC access
POLICY=$(cat <<POL
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontOAC",
      "Effect": "Allow",
      "Principal": {"Service": "cloudfront.amazonaws.com"},
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BUCKET/*",
      "Condition": {"StringEquals": {"AWS:SourceArn": "arn:aws:cloudfront::$(aws sts get-caller-identity --query Account --output text):distribution/$DIST_ID"}}
    }
  ]
}
POL)

aws s3api put-bucket-policy --bucket "$BUCKET" --policy "$POLICY"

# Upload files with cache headers
aws s3 sync . s3://"$BUCKET" \
  --exclude "*" \
  --include "index.html" \
  --include "frontend-*.html" \
  --include "frontend-config.js" \
  --acl private \
  --cache-control "no-cache, no-store, must-revalidate"

aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"

echo "\n✅ Frontend deployed"
echo "CloudFront domain: https://$DIST_DOMAIN"
echo "Open: https://$DIST_DOMAIN/index.html"

