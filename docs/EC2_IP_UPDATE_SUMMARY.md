# EC2 IP Address Update Summary

## Update Details
- **Old IP**: 43.209.12.182
- **New IP**: 43.209.22.250
- **Update Date**: 2025-08-13

## What Was Updated

### 1. Core Configuration Files
- ✅ `pm2-ecosystem.config.js` - Updated sensor-location-mapping service IPs
- ✅ `.env.ec2` files - Updated EC2 database host configurations
- ✅ `.env.dual-write` - Updated dual-write EC2 host configurations

### 2. ROS/GIS Integration Service
- ✅ All deployment scripts (`deploy-docker-ec2.sh`, `deploy-docker-ec2-remote-build.sh`)
- ✅ Security group documentation (`SECURITY_GROUP_UPDATE.md`, `SECURITY_GROUP_UPDATE_GUIDE.md`)
- ✅ Test scripts (`test-port-access.sh`)
- ✅ Python scripts for security group updates (`update-sg-boto3.py`)

### 3. Database Connection Configurations
- ✅ `services/sensor-data/src/config/dual-write.config.ts`
- ✅ All environment files referencing EC2 databases

### 4. Documentation
- ✅ All deployment guides and documentation
- ✅ GitHub workflow files
- ✅ Service-specific documentation

### 5. Scripts
- ✅ All shell scripts for deployment and migration
- ✅ Python scripts for data migration
- ✅ SQL scripts with connection strings

## Total Files Updated
- Over 220 files were successfully updated with the new IP address

## Next Steps

### 1. Verify EC2 Instance
Before using the services, ensure:
- The EC2 instance at `43.209.22.250` is running
- SSH access is configured: `ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250`
- Security groups are properly configured for the new instance

### 2. Test Database Connections
Test PostgreSQL/TimescaleDB connections:
```bash
PGPASSWORD=postgres123 psql -h 43.209.22.250 -p 5432 -U postgres -d sensor_data -c "SELECT 1"
```

### 3. Deploy Services
Once the EC2 instance is accessible, deploy the ROS/GIS Integration service:
```bash
cd services/ros-gis-integration
./scripts/deploy-docker-ec2-remote-build.sh
```

### 4. Update Security Groups
Remember to update the security group for the new EC2 instance to allow:
- Port 22 (SSH)
- Port 3022 (ROS/GIS Integration Service)
- Port 5432 (PostgreSQL)
- Other service-specific ports as needed

## Important Notes
- All references to the old IP (43.209.12.182) have been replaced
- No files remain with the old IP address
- The update was performed using automated scripts to ensure consistency
- Backup of original files (*.bak) were created and removed during the update process