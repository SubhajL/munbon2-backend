# Claude Instance 10: Dashboard BFF Service

## Scope of Work
This instance handles the Backend-for-Frontend service for comprehensive dashboards, data visualization, and aggregated views for different user roles.

## Assigned Components

### 1. **Dashboard BFF Service** (Primary)
- **Path**: `/services/bff-dashboard`
- **Port**: 4004
- **Responsibilities**:
  - Multi-role dashboard data aggregation
  - KPI calculations and metrics
  - Real-time data streaming
  - Historical data analysis
  - Report generation
  - Custom widget data providers

### 2. **Dashboard Types**
- **Farmer Dashboard**: Field status, irrigation schedules
- **Operator Dashboard**: System control, real-time monitoring
- **Manager Dashboard**: Performance metrics, resource allocation
- **Executive Dashboard**: High-level KPIs, trends

## Environment Setup

```bash
# Dashboard BFF Service
cat > services/bff-dashboard/.env.local << EOF
SERVICE_NAME=bff-dashboard
PORT=4004
NODE_ENV=development

# GraphQL Configuration
GRAPHQL_PATH=/graphql
GRAPHQL_PLAYGROUND=true
ENABLE_QUERY_BATCHING=true
QUERY_COMPLEXITY_LIMIT=1000

# WebSocket for real-time
WS_PORT=4104
WS_PATH=/ws/dashboard

# Internal Services (Read-only access)
SENSOR_SERVICE_URL=http://localhost:3003
WATER_LEVEL_SERVICE_URL=http://localhost:3008
MOISTURE_SERVICE_URL=http://localhost:3005
WEATHER_SERVICE_URL=http://localhost:3006
GIS_SERVICE_URL=http://localhost:3007
ROS_SERVICE_URL=http://localhost:3047
ANALYTICS_SERVICE_URL=http://localhost:3030
ALERT_SERVICE_URL=http://localhost:3032
REPORT_SERVICE_URL=http://localhost:3018

# Time-series Configuration
TIMESERIES_DEFAULT_INTERVAL=5m
TIMESERIES_MAX_POINTS=1000
AGGREGATION_FUNCTIONS=avg,min,max,sum,count

# Dashboard Configuration
REFRESH_INTERVALS=5s,30s,1m,5m,15m,30m,1h
DEFAULT_REFRESH_INTERVAL=30s
MAX_WIDGETS_PER_DASHBOARD=50
WIDGET_DATA_CACHE_TTL=30

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=12
CACHE_TTL_REALTIME=5
CACHE_TTL_AGGREGATED=300
CACHE_TTL_STATIC=3600

# Performance
MAX_CONCURRENT_QUERIES=20
QUERY_TIMEOUT_MS=10000
USE_DATALOADER=true
BATCH_INTERVAL_MS=10
EOF
```

## GraphQL Schema

```graphql
type Query {
  # Dashboard Configurations
  getDashboard(id: ID!): Dashboard!
  getDashboardsByRole(role: UserRole!): [Dashboard!]!
  getAvailableWidgets(dashboardType: DashboardType!): [WidgetDefinition!]!
  
  # Real-time Data
  getSystemOverview: SystemOverview!
  getCurrentMetrics(metricIds: [ID!]!): [Metric!]!
  getAlertsSummary(severity: AlertSeverity): AlertsSummary!
  
  # KPIs and Analytics
  getKPIs(period: PeriodInput!): KPIReport!
  getEfficiencyMetrics(zoneId: ID, period: PeriodInput!): EfficiencyReport!
  getResourceUtilization: ResourceUtilization!
  
  # Time-series Data
  getTimeSeries(input: TimeSeriesInput!): TimeSeries!
  getMultipleTimeSeries(inputs: [TimeSeriesInput!]!): [TimeSeries!]!
  
  # Aggregated Views
  getFarmerDashboard(farmerId: ID!): FarmerDashboard!
  getOperatorDashboard(operatorId: ID!): OperatorDashboard!
  getManagerDashboard(zoneId: ID): ManagerDashboard!
  getExecutiveDashboard: ExecutiveDashboard!
  
  # Custom Queries
  getWidgetData(widgetId: ID!, params: JSON): WidgetData!
  executeCustomQuery(query: CustomQueryInput!): JSON!
}

type Subscription {
  # Real-time Updates
  dashboardUpdates(dashboardId: ID!): DashboardUpdate!
  metricUpdates(metricIds: [ID!]!): MetricUpdate!
  alertStream(severity: AlertSeverity): Alert!
  
  # Widget-specific
  widgetDataStream(widgetId: ID!): WidgetDataUpdate!
  
  # System Status
  systemStatusStream: SystemStatus!
}

# Dashboard Types
type FarmerDashboard {
  farmer: Farmer!
  fields: [FieldStatus!]!
  irrigationSchedule: IrrigationSchedule!
  waterUsage: WaterUsageStats!
  weatherForecast: WeatherSummary!
  alerts: [Alert!]!
  recommendations: [Recommendation!]!
}

type OperatorDashboard {
  systemStatus: SystemStatus!
  activeDevices: DeviceStatusSummary!
  currentFlows: [FlowStatus!]!
  waterLevels: [WaterLevelStatus!]!
  activeAlarms: [Alarm!]!
  commandQueue: [PendingCommand!]!
  shiftReport: ShiftReport!
}

type ManagerDashboard {
  zoneOverview: ZoneOverview!
  performanceMetrics: PerformanceMetrics!
  waterBalance: WaterBalance!
  operationalEfficiency: EfficiencyMetrics!
  costAnalysis: CostReport!
  complianceStatus: ComplianceReport!
  trends: [TrendAnalysis!]!
}

type ExecutiveDashboard {
  kpis: [KPI!]!
  systemHealth: SystemHealthScore!
  waterSavings: WaterSavingsReport!
  cropYieldForecast: YieldForecast!
  financialSummary: FinancialSummary!
  sustainabilityMetrics: SustainabilityReport!
  alerts: [ExecutiveAlert!]!
}

# Widget System
type WidgetData {
  widgetId: ID!
  type: WidgetType!
  data: JSON!
  metadata: WidgetMetadata!
  lastUpdated: DateTime!
  nextUpdate: DateTime!
}

enum WidgetType {
  CHART
  GAUGE
  MAP
  TABLE
  STAT_CARD
  TIMELINE
  HEATMAP
}
```

## Dashboard Data Aggregation

### 1. Farmer Dashboard Aggregation
```javascript
async function getFarmerDashboard(farmerId) {
  // Parallel fetch all required data
  const [
    farmer,
    fields,
    schedule,
    waterUsage,
    weather,
    alerts
  ] = await Promise.all([
    userService.getFarmer(farmerId),
    gisService.getFieldsByOwner(farmerId),
    scheduleService.getFarmerSchedule(farmerId),
    analyticsService.getWaterUsage(farmerId, 'month'),
    weatherService.getForecast(farmer.location, 5),
    alertService.getFarmerAlerts(farmerId)
  ]);
  
  // Calculate recommendations
  const recommendations = await generateRecommendations({
    fields,
    waterUsage,
    weather,
    schedule
  });
  
  // Aggregate field status
  const fieldStatus = await Promise.all(
    fields.map(async field => ({
      ...field,
      moisture: await moistureService.getFieldMoisture(field.id),
      lastIrrigation: await getLastIrrigation(field.id),
      nextIrrigation: schedule.find(s => s.fieldId === field.id)?.nextDate
    }))
  );
  
  return {
    farmer,
    fields: fieldStatus,
    irrigationSchedule: schedule,
    waterUsage,
    weatherForecast: weather,
    alerts,
    recommendations
  };
}
```

### 2. Real-time Metrics Aggregation
```javascript
class MetricsAggregator {
  async getSystemOverview() {
    const metrics = await this.batchFetch([
      { service: 'water', metric: 'totalFlow' },
      { service: 'water', metric: 'activeGates' },
      { service: 'sensor', metric: 'onlineSensors' },
      { service: 'alert', metric: 'activeAlerts' }
    ]);
    
    return {
      timestamp: new Date(),
      waterFlow: {
        current: metrics.totalFlow.value,
        unit: 'm³/s',
        trend: metrics.totalFlow.trend
      },
      activeDevices: {
        gates: metrics.activeGates.count,
        pumps: metrics.activePumps.count,
        sensors: metrics.onlineSensors.count
      },
      systemHealth: this.calculateHealthScore(metrics),
      alerts: {
        critical: metrics.activeAlerts.critical,
        warning: metrics.activeAlerts.warning,
        info: metrics.activeAlerts.info
      }
    };
  }
  
  calculateHealthScore(metrics) {
    const weights = {
      sensorAvailability: 0.3,
      deviceResponsiveness: 0.3,
      dataFreshness: 0.2,
      alertRate: 0.2
    };
    
    // Calculate weighted score
    return Object.entries(weights).reduce((score, [metric, weight]) => {
      return score + (metrics[metric]?.score || 0) * weight;
    }, 0);
  }
}
```

### 3. Time-series Data Provider
```javascript
async function getTimeSeries({ metric, start, end, interval, aggregation }) {
  // Determine data source
  const source = getDataSource(metric);
  
  // Fetch raw data
  const rawData = await source.query({
    metric,
    start,
    end,
    interval: interval || 'auto'
  });
  
  // Apply aggregation
  const aggregated = aggregate(rawData, {
    function: aggregation || 'avg',
    interval: interval || calculateInterval(start, end)
  });
  
  // Add metadata
  return {
    metric,
    data: aggregated,
    metadata: {
      start,
      end,
      interval,
      aggregation,
      unit: getUnit(metric),
      count: aggregated.length
    }
  };
}
```

## Widget System

```javascript
class WidgetDataProvider {
  async getWidgetData(widgetId, params) {
    const widget = await getWidgetDefinition(widgetId);
    
    switch (widget.type) {
      case 'CHART':
        return this.getChartData(widget, params);
      case 'MAP':
        return this.getMapData(widget, params);
      case 'GAUGE':
        return this.getGaugeData(widget, params);
      // ... other widget types
    }
  }
  
  async getChartData(widget, params) {
    const series = await Promise.all(
      widget.series.map(s => 
        this.getTimeSeries({
          metric: s.metric,
          ...params
        })
      )
    );
    
    return {
      type: 'line',
      series,
      options: widget.chartOptions
    };
  }
}
```

## Performance Optimization

```javascript
// DataLoader for batching
const metricLoader = new DataLoader(async (keys) => {
  const results = await analyticsService.batchGetMetrics(keys);
  return keys.map(key => results.find(r => r.id === key));
});

// Query complexity analysis
const depthLimit = 5;
const complexityLimit = 1000;

const complexityAnalysis = {
  scalarCost: 1,
  objectCost: 2,
  listFactor: 10,
  introspectionCost: 1000
};
```

## API Endpoints

```
POST /graphql - Main GraphQL endpoint
WS /ws/dashboard - WebSocket for real-time updates
GET /api/v1/dashboard/export/{dashboardId} - Export dashboard
POST /api/v1/dashboard/screenshot - Generate dashboard screenshot
GET /api/v1/dashboard/templates - Dashboard templates
```

## Current Status
- ❌ Service structure: Not created
- ❌ Dashboard aggregation: Not implemented
- ❌ Widget system: Not built
- ❌ Real-time streaming: Not implemented
- ❌ Performance optimization: Not configured

## Priority Tasks
1. Set up GraphQL with DataLoader
2. Implement role-based dashboards
3. Build widget data providers
4. Create real-time WebSocket server
5. Implement caching strategies
6. Build metric aggregation engine
7. Create dashboard templates
8. Implement export functionality

## Testing Commands

```bash
# Get farmer dashboard
curl -X POST http://localhost:4004/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer farmer-token" \
  -d '{
    "query": "query { getFarmerDashboard(farmerId: \"F123\") { fields { id name moisture { current } } waterUsage { total } } }"
  }'

# Subscribe to real-time metrics
wscat -c ws://localhost:4104/ws/dashboard \
  -H "Authorization: Bearer token" \
  -x '{"type":"subscribe","subscription":"metricUpdates","variables":{"metricIds":["water-flow","active-gates"]}}'

# Get executive KPIs
curl -X POST http://localhost:4004/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer executive-token" \
  -d '{
    "query": "query { getExecutiveDashboard { kpis { name value trend target } waterSavings { total percentage } } }"
  }'
```

## Notes for Development
- Implement aggressive caching
- Use DataLoader for N+1 prevention
- Support configurable refresh rates
- Implement query complexity limits
- Add response compression
- Support offline data export
- Implement dashboard sharing
- Add anomaly detection for metrics