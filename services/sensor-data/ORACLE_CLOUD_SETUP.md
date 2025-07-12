# Oracle Cloud Free Tier Setup Guide

This guide will help you deploy the Munbon Unified API to Oracle Cloud Free Tier and connect it with your AWS Lambda.

## Prerequisites

1. Oracle Cloud account with Free Tier
2. OCI CLI installed and configured
3. AWS CLI installed (for Lambda updates)
4. SSH key pair for instance access

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   AWS Lambda    │────▶│  Oracle Cloud    │────▶│   Databases     │
│  (API Gateway)  │     │  (Unified API)   │     │  (TimescaleDB)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Quick Start

### Option 1: Automated Deployment (Recommended)

1. **Install OCI CLI** (if not already installed):
   ```bash
   bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
   ```

2. **Configure OCI CLI**:
   ```bash
   oci setup config
   ```

3. **Run the deployment script**:
   ```bash
   chmod +x deploy-oracle-free-tier.sh
   ./deploy-oracle-free-tier.sh
   ```

### Option 2: Manual Quick Deploy

If you already have an Oracle Cloud instance:

1. **Set instance IP**:
   ```bash
   export ORACLE_INSTANCE_IP=your.oracle.instance.ip
   ```

2. **Run quick deploy**:
   ```bash
   chmod +x quick-deploy-oracle.sh
   ./quick-deploy-oracle.sh
   ```

## Manual Setup Steps

### 1. Create Oracle Cloud Instance

1. Log in to Oracle Cloud Console
2. Navigate to Compute → Instances
3. Click "Create Instance"
4. Configure:
   - **Name**: munbon-unified-api
   - **Shape**: VM.Standard.E2.1.Micro (Always Free)
   - **Image**: Oracle Linux 8
   - **VCN**: Create new or use existing
   - **Subnet**: Public subnet
   - **SSH keys**: Upload your public key

### 2. Configure Security Rules

Add ingress rules for:
- **SSH**: Port 22 (0.0.0.0/0)
- **HTTP**: Port 80 (0.0.0.0/0)
- **HTTPS**: Port 443 (0.0.0.0/0)
- **API**: Port 3000 (0.0.0.0/0)

### 3. Install Docker on Instance

SSH to your instance:
```bash
ssh -i ~/.ssh/your-key opc@your-instance-ip
```

Install Docker:
```bash
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

# Add user to docker group
sudo usermod -aG docker opc
```

### 4. Deploy Application

1. **Create application directory**:
   ```bash
   sudo mkdir -p /opt/munbon-api
   sudo chown opc:opc /opt/munbon-api
   cd /opt/munbon-api
   ```

2. **Create docker-compose.yml**:
   ```yaml
   version: '3.8'
   
   services:
     unified-api:
       image: node:18-alpine
       container_name: munbon-unified-api
       restart: always
       ports:
         - "3000:3000"
       environment:
         - NODE_ENV=production
         - PORT=3000
         - INTERNAL_API_KEY=munbon-internal-f3b89263126548
         - TIMESCALE_HOST=your-timescale-host
         - TIMESCALE_PORT=5433
         - TIMESCALE_DB=sensor_data
         - TIMESCALE_USER=postgres
         - TIMESCALE_PASSWORD=your-password
         - MSSQL_HOST=moonup.hopto.org
         - MSSQL_PORT=1433
         - MSSQL_DB=db_scada
         - MSSQL_USER=sa
         - MSSQL_PASSWORD=bangkok1234
       volumes:
         - ./src:/app/src
         - ./package.json:/app/package.json
       working_dir: /app
       command: sh -c "npm install --production && node src/unified-api-v2.js"
   ```

3. **Copy application files** and start:
   ```bash
   # Copy your files then:
   sudo docker-compose up -d
   ```

### 5. Configure Reverse Proxy (Optional)

Install and configure Caddy for SSL:
```bash
# Install Caddy
sudo dnf install -y 'dnf-command(copr)'
sudo dnf copr enable @caddy/caddy -y
sudo dnf install -y caddy

# Configure Caddy
sudo tee /etc/caddy/Caddyfile << EOF
your-domain.com {
    reverse_proxy localhost:3000
}
EOF

# Start Caddy
sudo systemctl enable --now caddy
```

### 6. Update AWS Lambda

Update your Lambda environment variables:
```bash
aws lambda update-function-configuration \
    --function-name munbon-sensor-handler \
    --environment "Variables={
        UNIFIED_API_URL=http://your-oracle-ip:3000,
        INTERNAL_API_KEY=munbon-internal-f3b89263126548
    }" \
    --region ap-southeast-1
```

## Environment Variables

### Required Variables

| Variable | Description | Default |
|----------|-------------|---------|
| INTERNAL_API_KEY | Internal authentication key | munbon-internal-f3b89263126548 |
| TIMESCALE_HOST | TimescaleDB host | localhost |
| TIMESCALE_PORT | TimescaleDB port | 5433 |
| TIMESCALE_DB | TimescaleDB database | sensor_data |
| TIMESCALE_USER | TimescaleDB user | postgres |
| TIMESCALE_PASSWORD | TimescaleDB password | postgres |
| MSSQL_HOST | MSSQL host for AOS data | moonup.hopto.org |
| MSSQL_PORT | MSSQL port | 1433 |
| MSSQL_DB | MSSQL database | db_scada |
| MSSQL_USER | MSSQL user | sa |
| MSSQL_PASSWORD | MSSQL password | bangkok1234 |

## Testing

### 1. Test Health Endpoint
```bash
curl http://your-oracle-ip:3000/health
```

### 2. Test API Endpoint
```bash
curl -X GET http://your-oracle-ip:3000/api/v1/sensors/water-level/latest \
  -H "x-internal-key: munbon-internal-f3b89263126548"
```

### 3. Test Through Lambda
```bash
curl https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest \
  -H "x-api-key: your-api-key"
```

## Monitoring

### View Logs
```bash
ssh -i ~/.ssh/your-key opc@your-instance-ip
sudo docker-compose logs -f unified-api
```

### Check Status
```bash
sudo docker-compose ps
```

### Restart Service
```bash
sudo docker-compose restart unified-api
```

## Troubleshooting

### 1. Connection Refused
- Check security list rules
- Verify Docker is running: `sudo systemctl status docker`
- Check container logs: `sudo docker-compose logs`

### 2. Database Connection Issues
- Verify database credentials
- Check network connectivity from Oracle Cloud
- Ensure databases are accessible from Oracle Cloud IP

### 3. Lambda Connection Issues
- Verify UNIFIED_API_URL in Lambda environment
- Check INTERNAL_API_KEY matches
- Test direct connection to Oracle instance

## Security Considerations

1. **Firewall**: Only allow necessary ports
2. **API Key**: Use strong internal API key
3. **SSL**: Configure SSL with Caddy for production
4. **Updates**: Keep system and Docker updated
5. **Monitoring**: Set up monitoring for the instance

## Cost Optimization

Oracle Cloud Free Tier includes:
- 2 AMD-based Compute VMs with 1/8 OCPU and 1 GB memory each
- 2 Block Volumes, 200 GB total
- 10 GB Object Storage
- 10 GB Archive Storage
- 10 TB outbound data transfer per month

Stay within these limits to maintain free usage.

## Next Steps

1. Set up domain name and SSL
2. Configure monitoring and alerts
3. Set up automated backups
4. Implement rate limiting
5. Add application-level monitoring