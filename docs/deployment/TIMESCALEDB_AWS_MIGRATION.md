# TimescaleDB AWS Migration Guide & Cost Analysis

## Overview
This document provides recommendations for migrating TimescaleDB to AWS with detailed configurations and cost breakdowns for the Munbon Irrigation Control System.

## Current Data Profile
Based on the sensor data patterns:
- **Water Level Sensors**: ~10 sensors, data every minute
- **Moisture Sensors**: ~10 sensors, data every minute
- **Data Size**: ~1.5 KB per reading
- **Monthly Data Volume**: ~25 GB/month
- **Retention**: 2 years suggested (600 GB total)

## Option 1: EC2 Self-Managed (Recommended)

### Configuration
```yaml
Instance Type: t3.medium or t3.large
- t3.medium: 2 vCPU, 4 GB RAM
- t3.large: 2 vCPU, 8 GB RAM

Storage: EBS gp3
- 100 GB initial (expandable)
- 3000 IOPS baseline
- 125 MB/s throughput

OS: Ubuntu 22.04 LTS
Database: PostgreSQL 14 + TimescaleDB 2.x
```

### Monthly Costs (us-west-2)
```
t3.medium Instance:
- On-Demand: $0.0416/hour × 730 hours = $30.37/month
- 1-Year Reserved: ~$19.00/month (37% savings)
- 3-Year Reserved: ~$12.00/month (60% savings)

t3.large Instance:
- On-Demand: $0.0832/hour × 730 hours = $60.74/month
- 1-Year Reserved: ~$38.00/month
- 3-Year Reserved: ~$24.00/month

Storage (100 GB gp3):
- $0.08/GB × 100 GB = $8.00/month

Backup Storage (S3):
- 100 GB snapshots: $2.30/month

Data Transfer:
- First 1 GB/month: Free
- Up to 10 TB/month: $0.09/GB
- Estimated 50 GB/month = $4.50/month

Total Monthly Cost:
- t3.medium: $30.37 + $8 + $2.30 + $4.50 = $45.17/month
- t3.large: $60.74 + $8 + $2.30 + $4.50 = $75.54/month
```

### Setup Script
```bash
#!/bin/bash
# Install PostgreSQL and TimescaleDB
sudo apt update
sudo apt install -y postgresql-14 postgresql-contrib-14

# Add TimescaleDB repository
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt update

# Install TimescaleDB
sudo apt install -y timescaledb-2-postgresql-14
sudo timescaledb-tune --quiet --yes

# Configure PostgreSQL for remote access
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/14/main/postgresql.conf
echo "host    all    all    0.0.0.0/0    md5" | sudo tee -a /etc/postgresql/14/main/pg_hba.conf

# Restart PostgreSQL
sudo systemctl restart postgresql

# Create database and enable TimescaleDB
sudo -u postgres psql <<EOF
CREATE DATABASE munbon_timescale;
\c munbon_timescale
CREATE EXTENSION IF NOT EXISTS timescaledb;
EOF
```

## Option 2: Amazon RDS for PostgreSQL + pg_partman

Since RDS doesn't support TimescaleDB, use native PostgreSQL partitioning.

### Configuration
```yaml
Instance Type: db.t3.medium or db.t4g.medium
- db.t3.medium: 2 vCPU, 4 GB RAM
- db.t4g.medium: 2 vCPU, 4 GB RAM (ARM-based, 20% cheaper)

Storage: gp3
- 100 GB allocated storage
- Auto-scaling enabled up to 1000 GB

Multi-AZ: No (for cost savings)
Backup: 7 days retention
```

### Monthly Costs
```
db.t3.medium:
- On-Demand: $0.068/hour × 730 hours = $49.64/month
- 1-Year Reserved: ~$31.00/month

db.t4g.medium (ARM):
- On-Demand: $0.054/hour × 730 hours = $39.42/month
- 1-Year Reserved: ~$25.00/month

Storage:
- 100 GB gp3: $0.115/GB × 100 = $11.50/month

Backup Storage:
- Included in base price (7 days)

Total Monthly Cost:
- db.t3.medium: $49.64 + $11.50 = $61.14/month
- db.t4g.medium: $39.42 + $11.50 = $50.92/month
```

### Partitioning Strategy (Alternative to TimescaleDB)
```sql
-- Create partitioned tables
CREATE TABLE water_level_readings (
    time TIMESTAMP NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    level_cm DECIMAL(6,2),
    -- other columns...
) PARTITION BY RANGE (time);

-- Create monthly partitions
CREATE TABLE water_level_readings_2025_01 
    PARTITION OF water_level_readings
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Install pg_partman for automatic partition management
CREATE EXTENSION pg_partman;
```

## Option 3: Amazon Timestream (Purpose-Built Time-Series)

### Configuration
```yaml
Memory Store: 1 GB (recent data)
Magnetic Store: Unlimited (historical data)
Data Retention:
- Memory: 24 hours
- Magnetic: 2 years
```

### Monthly Costs
```
Memory Store:
- $0.036/GB-hour × 1 GB × 730 hours = $26.28/month

Magnetic Store:
- $0.03/GB × 25 GB/month = $0.75/month
- Total after 24 months: $0.03 × 600 GB = $18/month

Writes:
- First 1 million writes free
- $0.50 per million writes
- ~1.3M writes/month = $0.65/month

Queries:
- $0.01/GB scanned
- Estimated 100 GB/month = $1.00/month

Total Monthly Cost:
- Initial: $26.28 + $0.75 + $0.65 + $1.00 = $28.68/month
- After 2 years: $26.28 + $18 + $0.65 + $1.00 = $45.93/month
```

## Option 4: Managed TimescaleDB Cloud

### Configuration
```yaml
Service: Timescale Cloud
Plan: Development or Small
Region: AWS ap-southeast-1 (Singapore)
```

### Monthly Costs
```
Development Plan:
- 0.5 CPU, 2 GB RAM
- 10 GB storage included
- $25/month

Small Plan:
- 1 CPU, 4 GB RAM
- 50 GB storage included
- Additional storage: $0.135/GB
- ~$100/month

Medium Plan:
- 2 CPU, 8 GB RAM
- 100 GB storage included
- ~$250/month
```

## Cost Comparison Summary

| Option | Initial Monthly Cost | 2-Year Monthly Cost | Pros | Cons |
|--------|---------------------|---------------------|------|------|
| EC2 t3.medium Self-Managed | $45.17 | $45.17 | Full control, Real TimescaleDB | Requires maintenance |
| EC2 t3.large Self-Managed | $75.54 | $75.54 | Better performance | Higher cost |
| RDS db.t4g.medium | $50.92 | $50.92 | Managed, Automated backups | No TimescaleDB |
| Amazon Timestream | $28.68 | $45.93 | Serverless, No maintenance | Different query language |
| Timescale Cloud Small | $100 | $100 | Fully managed TimescaleDB | Most expensive |

## Recommendation

### For Production: **EC2 t3.large Self-Managed**
- Best balance of performance and cost
- Full TimescaleDB features
- Can optimize and tune as needed
- Use Reserved Instances for 60% savings

### For Development/Testing: **EC2 t3.medium Self-Managed**
- Lowest cost with real TimescaleDB
- Adequate for development workload
- Easy to scale up when needed

### Migration Strategy: **Hybrid Approach**
1. Start with EC2 t3.medium for development
2. Keep critical real-time data (7 days) on EC2
3. Archive older data to S3 for cost savings
4. Use CloudFront for API caching

## Additional Cost Optimizations

### 1. Reserved Instances
```
1-Year All Upfront Reserved (t3.large):
- Upfront: $333
- Monthly equivalent: $27.75/month (54% savings)

3-Year All Upfront Reserved (t3.large):
- Upfront: $580
- Monthly equivalent: $16.11/month (73% savings)
```

### 2. Spot Instances for Dev/Test
```
t3.large Spot:
- Average: ~$0.025/hour (70% savings)
- Monthly: ~$18.25/month
- Risk: Can be terminated with 2-minute notice
```

### 3. Data Lifecycle Management
```sql
-- Compress older data
SELECT compress_chunk(i) FROM show_chunks('water_level_readings', older_than => INTERVAL '7 days') i;

-- Move to cheaper storage
SELECT move_chunk(i, 'cold_storage_tablespace') FROM show_chunks('water_level_readings', older_than => INTERVAL '30 days') i;
```

### 4. Connection Pooling
```yaml
# PgBouncer configuration to reduce connection overhead
[databases]
munbon = host=localhost port=5432 dbname=munbon_timescale

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

## Security Considerations

### VPC Configuration
```yaml
VPC:
  CIDR: 10.0.0.0/16
  
Subnets:
  Private: 10.0.1.0/24 (Database)
  Public: 10.0.2.0/24 (NAT Gateway)
  
Security Groups:
  Database:
    - Port 5432 from Application SG only
    - No public access
  
  Application:
    - Port 443/80 from Internet
    - Port 5432 to Database SG
```

### Backup Strategy
```bash
# Automated daily backups to S3
0 2 * * * /usr/bin/pg_dump -Fc munbon_timescale | aws s3 cp - s3://munbon-backups/timescale/$(date +%Y%m%d).dump

# Point-in-time recovery with WAL archiving
archive_mode = on
archive_command = 'aws s3 cp %p s3://munbon-backups/wal/%f'
```

## Monitoring & Alerts

### CloudWatch Metrics
- CPU Utilization > 80%
- Memory Usage > 85%
- Disk Space < 10%
- Connection Count > 80% of max
- Query Duration > 1 second

### Estimated Total AWS Bill

#### Minimal Setup (t3.medium)
```
EC2 Instance:        $30.37
Storage:             $8.00
Backups:             $2.30
Data Transfer:       $4.50
CloudWatch:          $2.00
----------------------------
Total:               $47.17/month
```

#### Recommended Setup (t3.large + optimizations)
```
EC2 Instance (1-yr): $38.00
Storage (gp3):       $8.00
Backups (S3):        $2.30
Data Transfer:       $4.50
CloudWatch:          $2.00
Load Balancer:       $18.00
----------------------------
Total:               $72.80/month
```

## Conclusion

For the Munbon project, **EC2 self-managed TimescaleDB** offers the best balance of:
- Cost effectiveness ($45-75/month)
- Full TimescaleDB features
- Scalability options
- Control over optimization

Start with t3.medium for development and scale to t3.large or larger for production based on actual usage patterns.