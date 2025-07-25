from prometheus_client import Counter, Histogram, Gauge, Info

# Service info
service_info = Info(
    'flow_monitoring_service',
    'Flow monitoring service information'
)

# Request metrics
http_requests_total = Counter(
    'flow_monitoring_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'flow_monitoring_http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# Sensor data metrics
sensor_readings_total = Counter(
    'flow_monitoring_sensor_readings_total',
    'Total sensor readings processed',
    ['sensor_type', 'location_id']
)

sensor_errors_total = Counter(
    'flow_monitoring_sensor_errors_total',
    'Total sensor reading errors',
    ['sensor_type', 'error_type']
)

# Flow metrics
current_flow_rate = Gauge(
    'flow_monitoring_current_flow_rate_cubic_meters_per_second',
    'Current flow rate in m³/s',
    ['location_id', 'channel_id']
)

total_volume = Gauge(
    'flow_monitoring_total_volume_cubic_meters',
    'Total volume in m³',
    ['location_id', 'period']
)

water_level = Gauge(
    'flow_monitoring_water_level_meters',
    'Current water level in meters',
    ['location_id']
)

# Anomaly detection metrics
anomalies_detected_total = Counter(
    'flow_monitoring_anomalies_detected_total',
    'Total anomalies detected',
    ['anomaly_type', 'location_id']
)

# Model metrics
model_predictions_total = Counter(
    'flow_monitoring_model_predictions_total',
    'Total model predictions made',
    ['model_type']
)

model_accuracy = Gauge(
    'flow_monitoring_model_accuracy',
    'Model accuracy percentage',
    ['model_type']
)

# Database metrics
db_operations_total = Counter(
    'flow_monitoring_db_operations_total',
    'Total database operations',
    ['operation', 'database', 'status']
)

db_operation_duration_seconds = Histogram(
    'flow_monitoring_db_operation_duration_seconds',
    'Database operation latency',
    ['operation', 'database']
)

# Gate control metrics
gate_operations_counter = Counter(
    'flow_monitoring_gate_operations_total',
    'Total gate operations',
    ['gate_id', 'operation', 'mode']
)

gate_mode_gauge = Gauge(
    'flow_monitoring_gate_mode',
    'Current gate mode (1=automated, 0=manual)',
    ['gate_id']
)

gate_opening_gauge = Gauge(
    'flow_monitoring_gate_opening_percentage',
    'Current gate opening percentage',
    ['gate_id']
)

# Hydraulic solver metrics
hydraulic_solver_iterations = Histogram(
    'flow_monitoring_hydraulic_solver_iterations',
    'Number of iterations for hydraulic solver convergence',
    buckets=(5, 10, 20, 50, 100, 200, 500)
)

hydraulic_verification_duration = Histogram(
    'flow_monitoring_hydraulic_verification_duration_seconds',
    'Time taken to verify hydraulic schedules'
)


def setup_metrics():
    """Initialize service metrics"""
    service_info.info({
        'version': '1.0.0',
        'service': 'flow-monitoring'
    })