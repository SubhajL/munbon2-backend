# Apache Kafka Deployment

This directory contains Kubernetes manifests for deploying Apache Kafka cluster for the Munbon Irrigation Project.

## Components

1. **Zookeeper**: Coordination service for Kafka (1 instance)
2. **Kafka**: Distributed event streaming platform (3 brokers)
3. **Schema Registry**: Schema management for Avro/JSON schemas
4. **Kafka Connect**: Integration framework for connecting Kafka with external systems
5. **Kafka UI**: Web interface for managing and monitoring Kafka

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Kafka UI      │     │ Schema Registry │     │  Kafka Connect  │
│   (Port 8080)   │     │   (Port 8081)   │     │   (Port 8083)   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                         │
         └───────────────────────┼─────────────────────────┘
                                 │
                      ┌──────────┴──────────┐
                      │   Kafka Cluster     │
                      │   (3 Brokers)       │
                      │   (Port 9092)       │
                      └──────────┬──────────┘
                                 │
                      ┌──────────┴──────────┐
                      │    Zookeeper        │
                      │   (Port 2181)       │
                      └─────────────────────┘
```

## Deployment

```bash
# Deploy all components
kubectl apply -f .

# Or deploy in order
kubectl apply -f 00-namespace.yaml
kubectl apply -f 01-zookeeper.yaml
kubectl apply -f 02-kafka.yaml
kubectl apply -f 03-schema-registry.yaml
kubectl apply -f 04-kafka-connect.yaml
kubectl apply -f 05-kafka-ui.yaml
```

## Topics

Run the topic creation script after deployment:
```bash
# From project root
./scripts/kafka/create-topics.sh
```

### Topic Categories

1. **Sensor Data Topics**
   - `sensor.water-level`: Water level sensor readings
   - `sensor.moisture`: Soil moisture sensor data
   - `sensor.weather`: Weather station data
   - `sensor.flow-meter`: Flow meter readings

2. **Control Command Topics**
   - `control.gate-commands`: Gate control commands
   - `control.pump-commands`: Pump control commands
   - `control.valve-commands`: Valve control commands

3. **System Event Topics**
   - `system.alerts`: System-wide alerts
   - `system.notifications`: User notifications
   - `system.audit-log`: Audit trail events

4. **Analytics Topics**
   - `analytics.water-usage`: Water consumption analytics
   - `analytics.irrigation-efficiency`: Efficiency metrics

5. **Integration Topics**
   - `integration.scada-events`: SCADA system events
   - `integration.weather-updates`: External weather data
   - `integration.crop-data`: Crop management data

## Access

### Internal Access
- Kafka: `kafka.munbon-kafka.svc.cluster.local:29092`
- Zookeeper: `zookeeper.munbon-kafka.svc.cluster.local:2181`
- Schema Registry: `http://schema-registry.munbon-kafka.svc.cluster.local:8081`
- Kafka Connect: `http://kafka-connect.munbon-kafka.svc.cluster.local:8083`

### External Access
- Kafka UI: `http://kafka.munbon.local` (via Ingress)
- Kafka Brokers: Via LoadBalancer service on port 9092

## Configuration

### Producer Configuration
```properties
bootstrap.servers=kafka.munbon-kafka.svc.cluster.local:29092
acks=all
retries=3
compression.type=lz4
```

### Consumer Configuration
```properties
bootstrap.servers=kafka.munbon-kafka.svc.cluster.local:29092
group.id=your-consumer-group
enable.auto.commit=false
auto.offset.reset=earliest
```

## Monitoring

### Check Cluster Health
```bash
# Pod status
kubectl get pods -n munbon-kafka

# Kafka broker logs
kubectl logs -n munbon-kafka kafka-0

# List topics
kubectl exec -n munbon-kafka kafka-0 -- kafka-topics --list --bootstrap-server localhost:9092
```

### Kafka UI
Access the Kafka UI at `http://kafka.munbon.local` to:
- View topics and partitions
- Monitor consumer groups
- Browse messages
- Manage schemas
- Configure connectors

## Scaling

### Scale Kafka Brokers
```bash
# Scale to 5 brokers
kubectl scale statefulset kafka -n munbon-kafka --replicas=5
```

### Scale Kafka Connect Workers
```bash
# Scale to 3 workers
kubectl scale deployment kafka-connect -n munbon-kafka --replicas=3
```

## Backup and Disaster Recovery

1. **Topic Configuration**: Backed up automatically in Zookeeper
2. **Messages**: Configure retention based on requirements
3. **Schemas**: Stored in `_schemas` topic with replication factor 3

## Security Notes

For production deployment:
1. Enable SSL/TLS encryption
2. Configure SASL authentication
3. Set up ACLs for topic access control
4. Use network policies to restrict access
5. Enable audit logging

## Troubleshooting

### Common Issues

1. **Broker not joining cluster**
   ```bash
   kubectl logs -n munbon-kafka kafka-0
   ```

2. **Schema Registry connection issues**
   ```bash
   kubectl logs -n munbon-kafka deployment/schema-registry
   ```

3. **Consumer lag**
   ```bash
   kubectl exec -n munbon-kafka kafka-0 -- kafka-consumer-groups \
     --bootstrap-server localhost:9092 --describe --group <group-id>
   ```