#!/bin/bash

# Master deployment script for Munbon Cloud APIs
# This script deploys:
# 1. RID-MS SHAPE file ingestion and data exposure
# 2. Sensor data exposure APIs (water level, moisture, weather)
# 3. Sets up all necessary AWS resources

set -e  # Exit on error

echo "=== Munbon Cloud API Deployment Script ==="
echo "This script will deploy all cloud APIs for external access"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check prerequisites
check_prerequisites() {
    echo "📋 Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}❌ AWS CLI is not installed${NC}"
        echo "Please install: https://aws.amazon.com/cli/"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}❌ AWS credentials not configured${NC}"
        echo "Please run: aws configure"
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js is not installed${NC}"
        echo "Please install Node.js 18+"
        exit 1
    fi
    
    # Check Serverless Framework
    if ! command -v serverless &> /dev/null; then
        echo -e "${YELLOW}⚠️  Installing Serverless Framework...${NC}"
        npm install -g serverless
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
    echo ""
}

# Function to deploy RID-MS services
deploy_rid_ms() {
    echo "🚀 Deploying RID-MS Services..."
    echo ""
    
    cd services/rid-ms
    
    # Install dependencies
    echo "📦 Installing RID-MS dependencies..."
    npm install
    
    # Build the service
    echo "🔨 Building RID-MS..."
    npm run build
    
    # Deploy AWS infrastructure
    echo "☁️  Deploying RID-MS to AWS..."
    cd deployments/aws
    
    # Package Lambda functions
    ./package-lambdas.sh
    
    # Deploy CloudFormation stack
    STACK_NAME="munbon-rid-ms-prod"
    aws cloudformation deploy \
        --template-file cloudformation.yaml \
        --stack-name $STACK_NAME \
        --parameter-overrides Environment=prod \
        --capabilities CAPABILITY_IAM \
        --no-fail-on-empty-changeset
    
    # Get outputs
    echo ""
    echo "📋 RID-MS Deployment Outputs:"
    aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
        --output table
    
    # Save endpoints
    EXTERNAL_API=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query "Stacks[0].Outputs[?OutputKey=='ExternalApiUrl'].OutputValue" \
        --output text)
    
    INTERNAL_API=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query "Stacks[0].Outputs[?OutputKey=='InternalApiUrl'].OutputValue" \
        --output text)
    
    cd ../../../..
    
    echo -e "${GREEN}✅ RID-MS deployed successfully${NC}"
    echo ""
}

# Function to deploy sensor data APIs
deploy_sensor_data() {
    echo "🚀 Deploying Sensor Data APIs..."
    echo ""
    
    cd services/sensor-data/deployments/aws-lambda
    
    # Check if ingestion is already deployed
    echo "📋 Checking existing deployments..."
    if serverless info --stage prod --config serverless.yml &> /dev/null; then
        echo -e "${YELLOW}⚠️  Sensor ingestion already deployed, skipping...${NC}"
    else
        echo "📦 Deploying sensor ingestion..."
        serverless deploy --stage prod --config serverless.yml
    fi
    
    # Deploy data exposure API
    echo "📦 Deploying data exposure API..."
    serverless deploy --stage prod --config serverless-data-api.yml
    
    # Get endpoints
    echo ""
    echo "📋 Sensor Data API Outputs:"
    DATA_API_URL=$(serverless info --stage prod --config serverless-data-api.yml | grep "endpoint:" | head -1 | awk '{print $2}')
    echo "Data API: $DATA_API_URL"
    
    cd ../../../..
    
    echo -e "${GREEN}✅ Sensor Data APIs deployed successfully${NC}"
    echo ""
}

# Function to set up API keys
setup_api_keys() {
    echo "🔐 Setting up API keys..."
    echo ""
    
    # Generate API keys
    cat > api-keys.json << EOF
{
  "apiKeys": [
    {
      "key": "rid-ms-prod-$(openssl rand -hex 16)",
      "name": "RID-MS Production",
      "organization": "Royal Irrigation Department",
      "allowedDataTypes": ["water_level", "moisture", "aos", "shapefile"],
      "allowedEndpoints": ["*"]
    },
    {
      "key": "tmd-weather-$(openssl rand -hex 16)",
      "name": "Thai Meteorological Department",
      "organization": "TMD",
      "allowedDataTypes": ["aos"],
      "allowedEndpoints": ["/api/v1/public/aos/*"]
    },
    {
      "key": "mobile-app-$(openssl rand -hex 16)",
      "name": "Munbon Mobile App",
      "organization": "Munbon Project",
      "allowedDataTypes": ["water_level", "moisture"],
      "allowedEndpoints": ["/api/v1/public/water-levels/*", "/api/v1/public/moisture/*"]
    },
    {
      "key": "test-dev-$(openssl rand -hex 16)",
      "name": "Development Testing",
      "organization": "Development",
      "allowedDataTypes": ["water_level", "moisture", "aos", "shapefile"],
      "allowedEndpoints": ["*"]
    }
  ]
}
EOF
    
    echo "📄 API keys generated in api-keys.json"
    echo -e "${YELLOW}⚠️  Please update Lambda environment variables with these keys${NC}"
    echo ""
}

# Function to create test scripts
create_test_scripts() {
    echo "🧪 Creating test scripts..."
    
    cat > test-apis.sh << 'EOF'
#!/bin/bash

# Test script for Munbon APIs

echo "=== Testing Munbon Cloud APIs ==="
echo ""

# Load API keys
if [ ! -f api-keys.json ]; then
    echo "❌ api-keys.json not found"
    exit 1
fi

# Extract test API key
TEST_KEY=$(cat api-keys.json | grep -A1 "Development Testing" | grep "key" | cut -d'"' -f4)

# Load endpoints
if [ ! -f deployment-summary.txt ]; then
    echo "❌ deployment-summary.txt not found"
    exit 1
fi

# Test functions
test_endpoint() {
    local name=$1
    local url=$2
    local api_key=$3
    
    echo "Testing $name..."
    response=$(curl -s -w "\n%{http_code}" -H "X-API-Key: $api_key" "$url")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ Success: $name"
        echo "$body" | jq . 2>/dev/null || echo "$body"
    else
        echo "❌ Failed: $name (HTTP $http_code)"
        echo "$body"
    fi
    echo ""
}

# Extract endpoints from deployment summary
DATA_API=$(grep "Sensor Data API:" deployment-summary.txt | awk '{print $4}')
RID_API=$(grep "RID-MS External API:" deployment-summary.txt | awk '{print $4}')

echo "📋 Testing with API Key: ${TEST_KEY:0:20}..."
echo ""

# Test Sensor Data APIs
echo "=== Sensor Data APIs ==="
test_endpoint "Water Levels Latest" "$DATA_API/api/v1/public/water-levels/latest" "$TEST_KEY"
test_endpoint "Moisture Latest" "$DATA_API/api/v1/public/moisture/latest" "$TEST_KEY"
test_endpoint "AOS Weather Latest" "$DATA_API/api/v1/public/aos/latest" "$TEST_KEY"

# Test RID-MS APIs
echo "=== RID-MS APIs ==="
test_endpoint "List Shapefiles" "$RID_API/api/v1/rid-ms/shapefiles" "$TEST_KEY"
test_endpoint "Zone 1 Parcels" "$RID_API/api/v1/rid-ms/zones/Zone1/parcels" "$TEST_KEY"
test_endpoint "Water Demand Summary" "$RID_API/api/v1/rid-ms/zones/Zone1/water-demand-summary" "$TEST_KEY"

echo "✅ API testing complete"
EOF
    
    chmod +x test-apis.sh
    
    echo -e "${GREEN}✅ Test scripts created${NC}"
    echo ""
}

# Function to create deployment summary
create_deployment_summary() {
    echo "📄 Creating deployment summary..."
    
    cat > deployment-summary.txt << EOF
Munbon Cloud API Deployment Summary
=====================================
Deployed: $(date)

🌐 API Endpoints
----------------

Sensor Data APIs:
- Sensor Data API: $DATA_API_URL
  - GET /api/v1/public/water-levels/latest
  - GET /api/v1/public/water-levels/timeseries?date=DD/MM/YYYY
  - GET /api/v1/public/water-levels/statistics?date=DD/MM/YYYY
  - GET /api/v1/public/moisture/latest
  - GET /api/v1/public/moisture/timeseries?date=DD/MM/YYYY
  - GET /api/v1/public/moisture/statistics?date=DD/MM/YYYY
  - GET /api/v1/public/aos/latest
  - GET /api/v1/public/aos/timeseries?date=DD/MM/YYYY
  - GET /api/v1/public/aos/statistics?date=DD/MM/YYYY

RID-MS APIs:
- RID-MS External API: $EXTERNAL_API
  - POST /api/external/shapefile/push (Bearer token auth)
  - GET /api/v1/rid-ms/shapefiles
  - GET /api/v1/rid-ms/zones/{zone}/parcels
  - GET /api/v1/rid-ms/zones/{zone}/water-demand-summary
  - GET /api/v1/rid-ms/shapefiles/{id}/geojson
  - GET /api/v1/rid-ms/parcels/search
  - GET /api/v1/rid-ms/parcels/{id}
  - PUT /api/v1/rid-ms/parcels/{id}

- RID-MS Internal API: $INTERNAL_API
  (For internal service communication)

🔑 Authentication
-----------------
All endpoints require authentication:
- Sensor Data APIs: Header "X-API-Key: your-api-key"
- RID-MS External Push: Header "Authorization: Bearer munbon-ridms-shape"
- RID-MS Query APIs: Header "X-API-Key: your-api-key"

📊 Example Usage
----------------

# Get latest water levels
curl -H "X-API-Key: your-api-key" \\
  $DATA_API_URL/api/v1/public/water-levels/latest

# Upload SHAPE file
curl -X POST \\
  -H "Authorization: Bearer munbon-ridms-shape" \\
  -H "Content-Type: application/json" \\
  -d '{"filename":"test.zip","content":"base64-content"}' \\
  $EXTERNAL_API/api/external/shapefile/push

# Get parcels by zone
curl -H "X-API-Key: your-api-key" \\
  $EXTERNAL_API/api/v1/rid-ms/zones/Zone1/parcels

📈 AWS Resources
----------------
- Lambda Functions: Check AWS Console > Lambda
- API Gateways: Check AWS Console > API Gateway
- CloudFormation Stacks: munbon-rid-ms-prod, munbon-sensor-ingestion-prod, munbon-data-api-prod
- S3 Buckets: munbon-rid-shapefiles-prod, munbon-shape-files-prod
- DynamoDB Tables: munbon-rid-ms-prod-parcels, munbon-rid-ms-prod-shapefiles

🧪 Testing
----------
Run: ./test-apis.sh

📱 Client Integration
--------------------
See api-keys.json for organization-specific API keys
Update Lambda environment variables with the API keys

⚠️  Important Notes
------------------
1. API keys in api-keys.json should be kept secure
2. Update Lambda functions with API keys for authentication
3. Monitor AWS billing for usage beyond free tier
4. Set up CloudWatch alarms for error monitoring
EOF
    
    echo -e "${GREEN}✅ Deployment summary created${NC}"
    echo ""
}

# Main deployment flow
main() {
    echo ""
    check_prerequisites
    
    echo "This will deploy:"
    echo "1. RID-MS SHAPE file ingestion and APIs"
    echo "2. Sensor data exposure APIs"
    echo "3. Generate API keys and test scripts"
    echo ""
    read -p "Continue with deployment? (y/n) " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 1
    fi
    
    echo ""
    
    # Deploy services
    deploy_rid_ms
    deploy_sensor_data
    
    # Set up API keys
    setup_api_keys
    
    # Create test scripts
    create_test_scripts
    
    # Create summary
    create_deployment_summary
    
    echo ""
    echo "========================================="
    echo -e "${GREEN}🎉 Deployment Complete!${NC}"
    echo "========================================="
    echo ""
    echo "📄 Files created:"
    echo "   - deployment-summary.txt (API endpoints and usage)"
    echo "   - api-keys.json (API keys for clients)"
    echo "   - test-apis.sh (Test script)"
    echo ""
    echo "🔧 Next steps:"
    echo "1. Update Lambda environment variables with API keys from api-keys.json"
    echo "2. Run ./test-apis.sh to test the APIs"
    echo "3. Share relevant API keys with client organizations"
    echo "4. Monitor AWS CloudWatch for logs and metrics"
    echo ""
}

# Run main function
main