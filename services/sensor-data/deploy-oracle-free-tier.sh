#!/bin/bash

# Oracle Cloud Free Tier Deployment Script
# This script sets up and deploys the unified API to Oracle Cloud Free Tier

set -e

echo "======================================"
echo "Oracle Cloud Free Tier Deployment"
echo "======================================"

# Configuration
ORACLE_REGION="ap-mumbai-1"  # Change to your region
COMPARTMENT_NAME="munbon-backend"
INSTANCE_NAME="munbon-unified-api"
SHAPE="VM.Standard.E2.1.Micro"  # Free tier shape
IMAGE_ID=""  # Will be set based on region
SUBNET_NAME="munbon-public-subnet"
VCN_NAME="munbon-vcn"
SECURITY_LIST_NAME="munbon-security-list"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to check if OCI CLI is installed
check_oci_cli() {
    if ! command -v oci &> /dev/null; then
        echo -e "${RED}OCI CLI is not installed. Please install it first:${NC}"
        echo "bash -c \"\$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)\""
        exit 1
    fi
    echo -e "${GREEN}✓ OCI CLI is installed${NC}"
}

# Function to get or create VCN
setup_vcn() {
    echo -e "${YELLOW}Setting up Virtual Cloud Network...${NC}"
    
    # Check if VCN exists
    VCN_ID=$(oci network vcn list --compartment-id $COMPARTMENT_ID --display-name "$VCN_NAME" --query 'data[0].id' --raw-output 2>/dev/null || echo "")
    
    if [ -z "$VCN_ID" ]; then
        echo "Creating VCN..."
        VCN_ID=$(oci network vcn create \
            --compartment-id $COMPARTMENT_ID \
            --display-name "$VCN_NAME" \
            --cidr-blocks '["10.0.0.0/16"]' \
            --wait-for-state AVAILABLE \
            --query 'data.id' \
            --raw-output)
        echo -e "${GREEN}✓ VCN created: $VCN_ID${NC}"
    else
        echo -e "${GREEN}✓ VCN already exists: $VCN_ID${NC}"
    fi
}

# Function to setup Internet Gateway
setup_internet_gateway() {
    echo -e "${YELLOW}Setting up Internet Gateway...${NC}"
    
    # Check if Internet Gateway exists
    IGW_ID=$(oci network internet-gateway list \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --display-name "munbon-igw" \
        --query 'data[0].id' \
        --raw-output 2>/dev/null || echo "")
    
    if [ -z "$IGW_ID" ]; then
        echo "Creating Internet Gateway..."
        IGW_ID=$(oci network internet-gateway create \
            --compartment-id $COMPARTMENT_ID \
            --vcn-id $VCN_ID \
            --display-name "munbon-igw" \
            --is-enabled true \
            --wait-for-state AVAILABLE \
            --query 'data.id' \
            --raw-output)
        echo -e "${GREEN}✓ Internet Gateway created: $IGW_ID${NC}"
    else
        echo -e "${GREEN}✓ Internet Gateway already exists: $IGW_ID${NC}"
    fi
}

# Function to setup Route Table
setup_route_table() {
    echo -e "${YELLOW}Setting up Route Table...${NC}"
    
    # Get default route table
    RT_ID=$(oci network route-table list \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --query 'data[0].id' \
        --raw-output)
    
    # Update route table with internet gateway route
    oci network route-table update \
        --rt-id $RT_ID \
        --route-rules "[{\"destination\": \"0.0.0.0/0\", \"destinationType\": \"CIDR_BLOCK\", \"networkEntityId\": \"$IGW_ID\"}]" \
        --force
    
    echo -e "${GREEN}✓ Route table updated${NC}"
}

# Function to setup Security List
setup_security_list() {
    echo -e "${YELLOW}Setting up Security List...${NC}"
    
    # Get default security list
    SL_ID=$(oci network security-list list \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --query 'data[0].id' \
        --raw-output)
    
    # Define ingress rules
    INGRESS_RULES='[
        {
            "protocol": "6",
            "source": "0.0.0.0/0",
            "tcpOptions": {
                "destinationPortRange": {
                    "min": 22,
                    "max": 22
                }
            }
        },
        {
            "protocol": "6",
            "source": "0.0.0.0/0",
            "tcpOptions": {
                "destinationPortRange": {
                    "min": 80,
                    "max": 80
                }
            }
        },
        {
            "protocol": "6",
            "source": "0.0.0.0/0",
            "tcpOptions": {
                "destinationPortRange": {
                    "min": 443,
                    "max": 443
                }
            }
        },
        {
            "protocol": "6",
            "source": "0.0.0.0/0",
            "tcpOptions": {
                "destinationPortRange": {
                    "min": 3000,
                    "max": 3000
                }
            }
        }
    ]'
    
    # Update security list
    oci network security-list update \
        --security-list-id $SL_ID \
        --ingress-security-rules "$INGRESS_RULES" \
        --force
    
    echo -e "${GREEN}✓ Security list updated${NC}"
}

# Function to setup Subnet
setup_subnet() {
    echo -e "${YELLOW}Setting up Subnet...${NC}"
    
    # Check if subnet exists
    SUBNET_ID=$(oci network subnet list \
        --compartment-id $COMPARTMENT_ID \
        --vcn-id $VCN_ID \
        --display-name "$SUBNET_NAME" \
        --query 'data[0].id' \
        --raw-output 2>/dev/null || echo "")
    
    if [ -z "$SUBNET_ID" ]; then
        echo "Creating Subnet..."
        SUBNET_ID=$(oci network subnet create \
            --compartment-id $COMPARTMENT_ID \
            --vcn-id $VCN_ID \
            --display-name "$SUBNET_NAME" \
            --cidr-block "10.0.0.0/24" \
            --wait-for-state AVAILABLE \
            --query 'data.id' \
            --raw-output)
        echo -e "${GREEN}✓ Subnet created: $SUBNET_ID${NC}"
    else
        echo -e "${GREEN}✓ Subnet already exists: $SUBNET_ID${NC}"
    fi
}

# Function to get latest Oracle Linux image
get_oracle_linux_image() {
    echo -e "${YELLOW}Getting Oracle Linux image...${NC}"
    
    # Get the latest Oracle Linux 8 image
    IMAGE_ID=$(oci compute image list \
        --compartment-id $COMPARTMENT_ID \
        --operating-system "Oracle Linux" \
        --operating-system-version "8" \
        --shape "$SHAPE" \
        --sort-by TIMECREATED \
        --sort-order DESC \
        --query 'data[0].id' \
        --raw-output)
    
    echo -e "${GREEN}✓ Found image: $IMAGE_ID${NC}"
}

# Function to create compute instance
create_instance() {
    echo -e "${YELLOW}Creating compute instance...${NC}"
    
    # Check if instance exists
    INSTANCE_ID=$(oci compute instance list \
        --compartment-id $COMPARTMENT_ID \
        --display-name "$INSTANCE_NAME" \
        --lifecycle-state RUNNING \
        --query 'data[0].id' \
        --raw-output 2>/dev/null || echo "")
    
    if [ -z "$INSTANCE_ID" ]; then
        # Create SSH key if doesn't exist
        if [ ! -f ~/.ssh/munbon-oracle ]; then
            ssh-keygen -t rsa -b 4096 -f ~/.ssh/munbon-oracle -N ""
        fi
        
        echo "Creating instance..."
        INSTANCE_ID=$(oci compute instance launch \
            --compartment-id $COMPARTMENT_ID \
            --display-name "$INSTANCE_NAME" \
            --availability-domain "${AVAILABILITY_DOMAIN}" \
            --shape "$SHAPE" \
            --image-id "$IMAGE_ID" \
            --subnet-id "$SUBNET_ID" \
            --ssh-authorized-keys-file ~/.ssh/munbon-oracle.pub \
            --wait-for-state RUNNING \
            --query 'data.id' \
            --raw-output)
        echo -e "${GREEN}✓ Instance created: $INSTANCE_ID${NC}"
    else
        echo -e "${GREEN}✓ Instance already exists: $INSTANCE_ID${NC}"
    fi
}

# Function to get instance public IP
get_instance_ip() {
    echo -e "${YELLOW}Getting instance public IP...${NC}"
    
    # Get VNIC attachment
    VNIC_ID=$(oci compute vnic-attachment list \
        --compartment-id $COMPARTMENT_ID \
        --instance-id $INSTANCE_ID \
        --query 'data[0]."vnic-id"' \
        --raw-output)
    
    # Get public IP
    PUBLIC_IP=$(oci network vnic get \
        --vnic-id $VNIC_ID \
        --query 'data."public-ip"' \
        --raw-output)
    
    echo -e "${GREEN}✓ Public IP: $PUBLIC_IP${NC}"
}

# Function to setup instance
setup_instance() {
    echo -e "${YELLOW}Setting up instance...${NC}"
    
    # Create setup script
    cat > /tmp/setup-unified-api.sh << 'EOF'
#!/bin/bash
set -e

# Update system
sudo dnf update -y

# Install Docker
sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Setup firewall
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload

# Create app directory
sudo mkdir -p /opt/munbon-api
sudo chown opc:opc /opt/munbon-api

# Install Caddy for reverse proxy
sudo dnf install -y 'dnf-command(copr)'
sudo dnf copr enable @caddy/caddy -y
sudo dnf install -y caddy

# Configure Caddy
sudo tee /etc/caddy/Caddyfile > /dev/null << 'CADDY'
:80 {
    reverse_proxy localhost:3000
    
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        X-XSS-Protection "1; mode=block"
    }
    
    log {
        output file /var/log/caddy/access.log
    }
}
CADDY

# Enable and start Caddy
sudo systemctl enable caddy
sudo systemctl start caddy

echo "Instance setup complete!"
EOF

    # Copy and run setup script
    scp -i ~/.ssh/munbon-oracle -o StrictHostKeyChecking=no /tmp/setup-unified-api.sh opc@$PUBLIC_IP:/tmp/
    ssh -i ~/.ssh/munbon-oracle -o StrictHostKeyChecking=no opc@$PUBLIC_IP 'bash /tmp/setup-unified-api.sh'
    
    echo -e "${GREEN}✓ Instance setup complete${NC}"
}

# Function to deploy application
deploy_application() {
    echo -e "${YELLOW}Deploying unified API...${NC}"
    
    # Create deployment directory
    mkdir -p /tmp/munbon-deploy
    cp Dockerfile.oracle /tmp/munbon-deploy/Dockerfile
    cp src/unified-api-v2.js /tmp/munbon-deploy/
    cp package*.json /tmp/munbon-deploy/
    
    # Create docker-compose file
    cat > /tmp/munbon-deploy/docker-compose.yml << EOF
version: '3.8'

services:
  unified-api:
    build: .
    container_name: munbon-unified-api
    restart: always
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - PORT=3000
      - INTERNAL_API_KEY=${INTERNAL_API_KEY:-munbon-internal-f3b89263126548}
      - TIMESCALE_HOST=host.docker.internal
      - TIMESCALE_PORT=5433
      - TIMESCALE_DB=sensor_data
      - TIMESCALE_USER=postgres
      - TIMESCALE_PASSWORD=postgres
      - MSSQL_HOST=moonup.hopto.org
      - MSSQL_PORT=1433
      - MSSQL_DB=db_scada
      - MSSQL_USER=sa
      - MSSQL_PASSWORD=bangkok1234
    networks:
      - munbon-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  munbon-net:
    driver: bridge
EOF

    # Create .env file
    cat > /tmp/munbon-deploy/.env << EOF
# Internal API Key (used by AWS Lambda to authenticate)
INTERNAL_API_KEY=${INTERNAL_API_KEY:-munbon-internal-f3b89263126548}

# TimescaleDB Configuration
TIMESCALE_HOST=${TIMESCALE_HOST:-localhost}
TIMESCALE_PORT=${TIMESCALE_PORT:-5433}
TIMESCALE_DB=${TIMESCALE_DB:-sensor_data}
TIMESCALE_USER=${TIMESCALE_USER:-postgres}
TIMESCALE_PASSWORD=${TIMESCALE_PASSWORD:-postgres}

# MSSQL Configuration (for AOS weather data)
MSSQL_HOST=${MSSQL_HOST:-moonup.hopto.org}
MSSQL_PORT=${MSSQL_PORT:-1433}
MSSQL_DB=${MSSQL_DB:-db_scada}
MSSQL_USER=${MSSQL_USER:-sa}
MSSQL_PASSWORD=${MSSQL_PASSWORD:-bangkok1234}
EOF

    # Copy files to server
    scp -i ~/.ssh/munbon-oracle -r /tmp/munbon-deploy/* opc@$PUBLIC_IP:/opt/munbon-api/
    
    # Deploy with Docker Compose
    ssh -i ~/.ssh/munbon-oracle opc@$PUBLIC_IP << 'DEPLOY'
cd /opt/munbon-api
mkdir -p src
sudo docker-compose down || true
sudo docker-compose build
sudo docker-compose up -d
sudo docker-compose logs
DEPLOY
    
    echo -e "${GREEN}✓ Application deployed${NC}"
}

# Function to update AWS Lambda
update_lambda_env() {
    echo -e "${YELLOW}Updating AWS Lambda environment...${NC}"
    
    # Update Lambda environment variable with Oracle Cloud endpoint
    aws lambda update-function-configuration \
        --function-name munbon-sensor-handler \
        --environment "Variables={UNIFIED_API_URL=http://$PUBLIC_IP,INTERNAL_API_KEY=${INTERNAL_API_KEY:-munbon-internal-f3b89263126548}}" \
        --region ap-southeast-1 || true
    
    echo -e "${GREEN}✓ Lambda environment updated${NC}"
}

# Function to test connectivity
test_connectivity() {
    echo -e "${YELLOW}Testing connectivity...${NC}"
    
    # Test health endpoint
    echo "Testing health endpoint..."
    curl -s http://$PUBLIC_IP/health | jq .
    
    # Test from AWS Lambda URL
    echo -e "\nTesting through AWS Lambda..."
    curl -s https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest \
        -H "x-api-key: test-key-123" | jq .
    
    echo -e "${GREEN}✓ Connectivity test complete${NC}"
}

# Main execution
main() {
    echo "Starting Oracle Cloud deployment process..."
    
    # Check prerequisites
    check_oci_cli
    
    # Get compartment ID
    echo -e "${YELLOW}Getting compartment ID...${NC}"
    COMPARTMENT_ID=$(oci iam compartment list --query 'data[?name==`'$COMPARTMENT_NAME'`].id | [0]' --raw-output)
    if [ -z "$COMPARTMENT_ID" ]; then
        echo -e "${RED}Compartment not found. Creating...${NC}"
        COMPARTMENT_ID=$(oci iam compartment create \
            --name "$COMPARTMENT_NAME" \
            --description "Munbon Backend Infrastructure" \
            --wait-for-state ACTIVE \
            --query 'data.id' \
            --raw-output)
    fi
    echo -e "${GREEN}✓ Compartment ID: $COMPARTMENT_ID${NC}"
    
    # Get availability domain
    AVAILABILITY_DOMAIN=$(oci iam availability-domain list --query 'data[0].name' --raw-output)
    echo -e "${GREEN}✓ Availability Domain: $AVAILABILITY_DOMAIN${NC}"
    
    # Setup infrastructure
    setup_vcn
    setup_internet_gateway
    setup_route_table
    setup_security_list
    setup_subnet
    
    # Create instance
    get_oracle_linux_image
    create_instance
    get_instance_ip
    
    # Wait for instance to be ready
    echo "Waiting for instance to be ready..."
    sleep 30
    
    # Setup and deploy
    setup_instance
    deploy_application
    update_lambda_env
    
    # Test
    echo "Waiting for services to start..."
    sleep 20
    test_connectivity
    
    echo -e "\n${GREEN}======================================"
    echo "Deployment Complete!"
    echo "======================================"
    echo "Oracle Cloud Instance IP: $PUBLIC_IP"
    echo "Unified API URL: http://$PUBLIC_IP"
    echo "SSH Access: ssh -i ~/.ssh/munbon-oracle opc@$PUBLIC_IP"
    echo ""
    echo "Next steps:"
    echo "1. Configure DNS (optional): Point your domain to $PUBLIC_IP"
    echo "2. Setup SSL with Caddy: sudo caddy reload"
    echo "3. Monitor logs: ssh to instance and run 'sudo docker-compose logs -f'"
    echo "======================================${NC}"
}

# Run main function
main "$@"