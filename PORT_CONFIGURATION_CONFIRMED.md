# Port Configuration - CONFIRMED ✅

## Services Port Assignment (Matching Your Requirements)

### Infrastructure Services:
1. **PostgreSQL + PostGIS**: 5432 ✅
2. **MongoDB**: 27017 (not in Docker, run locally)
3. **Redis**: 6379 ✅
4. **InfluxDB**: 8086 (not in Docker, run locally)
5. **Apache Kafka**: 9092, 2181 (not in Docker, run locally)
6. **API Gateway (Kong)**: 8000, 8001 (not configured yet)

### Microservices (All Fixed):
| Service | Port | Status |
|---------|------|--------|
| Auth Service | 3001 | ✅ Fixed |
| Sensor Data Service | 3003 | ✅ Fixed |
| Sensor Data Consumer Dashboard | 3004 | ✅ Fixed |
| Moisture Monitoring | 3005 | ✅ Fixed |
| Weather Monitoring | 3006 | ✅ Fixed |
| GIS Service | 3007 | ✅ Fixed |
| Water Level Monitoring | 3008 | ✅ Fixed |
| ROS Service | 3047 | ✅ Fixed |

### Additional Services (Not in your list but in codebase):
- RID-MS: 3011
- AWD Control: 3013
- Flow Monitoring: 3014

## Docker Compose Configuration Updated

All port conflicts have been resolved in `docker-compose.ec2-consolidated.yml`:
- No more port conflicts
- All services aligned with your agreed port list
- Ready for deployment

## Next Steps:
1. Commit these changes
2. Push to GitHub to trigger automated deployment
3. Or manually deploy on EC2