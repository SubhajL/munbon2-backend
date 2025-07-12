#!/bin/bash

# Setup FREE dynamic API keys using AWS Parameter Store

echo "Setting up dynamic API keys with AWS Parameter Store (FREE)..."

# 1. Create parameter with current API keys
aws ssm put-parameter \
  --name "/munbon/api-keys" \
  --value "rid-ms-prod-key1,tmd-weather-key2,university-key3" \
  --type StringList \
  --description "Munbon Data API Keys" \
  --region ap-southeast-1 \
  --overwrite

echo "✅ Parameter created"

# 2. To add a new API key later:
echo ""
echo "To add new API keys, run:"
echo 'aws ssm put-parameter --name "/munbon/api-keys" --value "rid-ms-prod-key1,tmd-weather-key2,university-key3,new-org-key4" --type StringList --region ap-southeast-1 --overwrite'

# 3. To view current API keys:
echo ""
echo "To view current API keys:"
echo 'aws ssm get-parameter --name "/munbon/api-keys" --region ap-southeast-1 --query "Parameter.Value" --output text'

# 4. Example: Add a new organization
echo ""
echo "Example - Adding Department of Agriculture:"
echo 'CURRENT_KEYS=$(aws ssm get-parameter --name "/munbon/api-keys" --region ap-southeast-1 --query "Parameter.Value" --output text)'
echo 'aws ssm put-parameter --name "/munbon/api-keys" --value "$CURRENT_KEYS,agri-dept-key123" --type StringList --region ap-southeast-1 --overwrite'