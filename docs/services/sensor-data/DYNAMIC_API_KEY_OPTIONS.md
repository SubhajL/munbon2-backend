# Dynamic API Key Management Options

## Current Implementation
- API keys are stored in Lambda environment variable: `EXTERNAL_API_KEYS`
- Format: `'rid-ms-prod-key1,tmd-weather-key2,university-key3'`
- Fixed list, requires Lambda redeployment to change

## Option 1: DynamoDB Table (Recommended)
**Best for: Full control, audit trails, rate limiting**

### Implementation:
1. Create DynamoDB table for API keys:
```
Table: munbon-api-keys
- api_key (Primary Key)
- organization_name
- contact_email
- created_date
- expiry_date
- is_active
- rate_limit_per_minute
- allowed_endpoints (list)
- last_used
- usage_count
```

2. Update Lambda to check DynamoDB:
```typescript
import { DynamoDBClient, GetItemCommand } from "@aws-sdk/client-dynamodb";

const dynamodb = new DynamoDBClient({ region: 'ap-southeast-1' });

const validateApiKey = async (apiKey: string | undefined): Promise<boolean> => {
  if (!apiKey) return false;
  
  try {
    const command = new GetItemCommand({
      TableName: 'munbon-api-keys',
      Key: { api_key: { S: apiKey } }
    });
    
    const result = await dynamodb.send(command);
    if (!result.Item) return false;
    
    // Check if active and not expired
    const isActive = result.Item.is_active?.BOOL;
    const expiryDate = result.Item.expiry_date?.S;
    
    if (!isActive) return false;
    if (expiryDate && new Date(expiryDate) < new Date()) return false;
    
    // Update last_used timestamp
    await updateLastUsed(apiKey);
    
    return true;
  } catch (error) {
    console.error('API key validation error:', error);
    return false;
  }
};
```

### Benefits:
- Add/remove keys without redeployment
- Set expiration dates
- Track usage statistics
- Implement rate limiting
- Restrict access to specific endpoints

## Option 2: AWS Secrets Manager
**Best for: Security-focused, rotation policies**

### Implementation:
```typescript
import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";

const secretsManager = new SecretsManagerClient({ region: 'ap-southeast-1' });

const getValidApiKeys = async (): Promise<Set<string>> => {
  try {
    const command = new GetSecretValueCommand({
      SecretId: "munbon/api-keys"
    });
    
    const response = await secretsManager.send(command);
    const secrets = JSON.parse(response.SecretString || '{}');
    
    return new Set(Object.keys(secrets).filter(key => secrets[key].active));
  } catch (error) {
    console.error('Failed to load API keys:', error);
    return new Set();
  }
};
```

### Benefits:
- Secure storage with encryption
- Automatic rotation capabilities
- Audit trail through CloudTrail
- Version history

## Option 3: API Gateway API Keys
**Best for: AWS-native solution, usage plans**

### Implementation:
1. Create API keys in API Gateway
2. Create usage plans with throttling
3. Associate API keys with usage plans

```bash
# Create API key
aws apigateway create-api-key \
  --name "RID-Production" \
  --description "RID Main System Access" \
  --enabled

# Create usage plan
aws apigateway create-usage-plan \
  --name "Standard-Plan" \
  --throttle burstLimit=200,rateLimit=100 \
  --quota limit=10000,period=DAY
```

### Benefits:
- Built-in rate limiting and quotas
- No custom code needed
- AWS handles validation
- Usage metrics in CloudWatch

## Option 4: Parameter Store (Simple)
**Best for: Quick implementation, small scale**

### Implementation:
```typescript
import { SSMClient, GetParameterCommand } from "@aws-sdk/client-ssm";

const ssm = new SSMClient({ region: 'ap-southeast-1' });

const getValidApiKeys = async (): Promise<string[]> => {
  try {
    const command = new GetParameterCommand({
      Name: '/munbon/api-keys',
      WithDecryption: true
    });
    
    const response = await ssm.send(command);
    return response.Parameter?.Value?.split(',') || [];
  } catch (error) {
    console.error('Failed to load API keys:', error);
    return [];
  }
};
```

### Benefits:
- Simple to implement
- Can update without code changes
- Supports encryption
- Free for standard parameters

## Recommended Approach: DynamoDB + API Gateway

### Step 1: Create DynamoDB table
```bash
aws dynamodb create-table \
  --table-name munbon-api-keys \
  --attribute-definitions \
    AttributeName=api_key,AttributeType=S \
  --key-schema \
    AttributeName=api_key,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### Step 2: Add API key management endpoints
```typescript
// Admin endpoints (protected)
export const createApiKey = async (event: APIGatewayProxyEvent): Promise<APIGatewayProxyResult> => {
  // Generate new API key
  const apiKey = `mk-${uuidv4()}`;
  const body = JSON.parse(event.body || '{}');
  
  await dynamodb.send(new PutItemCommand({
    TableName: 'munbon-api-keys',
    Item: {
      api_key: { S: apiKey },
      organization_name: { S: body.organization },
      contact_email: { S: body.email },
      created_date: { S: new Date().toISOString() },
      is_active: { BOOL: true },
      rate_limit_per_minute: { N: body.rateLimit || '100' },
      usage_count: { N: '0' }
    }
  }));
  
  return createResponse(201, { api_key: apiKey });
};
```

### Step 3: Add key management CLI
```bash
# Create new API key
curl -X POST https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/admin/api-keys \
  -H "X-Admin-Key: admin-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "organization": "Department of Agriculture",
    "email": "admin@agriculture.go.th",
    "rateLimit": 1000
  }'

# List all API keys
curl https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/admin/api-keys \
  -H "X-Admin-Key: admin-secret-key"

# Revoke API key
curl -X DELETE https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/admin/api-keys/mk-12345 \
  -H "X-Admin-Key: admin-secret-key"
```

## Quick Start (Using Parameter Store)

1. Add current keys to Parameter Store:
```bash
aws ssm put-parameter \
  --name "/munbon/api-keys" \
  --value "rid-ms-prod-key1,tmd-weather-key2,university-key3,agri-dept-key4" \
  --type SecureString \
  --overwrite
```

2. Update Lambda to read from Parameter Store instead of environment variable
3. Grant Lambda IAM permission to read parameter:
```yaml
- Effect: Allow
  Action:
    - ssm:GetParameter
  Resource: 
    - arn:aws:ssm:ap-southeast-1:*:parameter/munbon/api-keys
```

This way, you can add new API keys without redeploying Lambda!