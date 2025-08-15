// K6 Load Test Script for Munbon Backend Services with EC2 Database
// Tests performance under load with EC2 latency considerations

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Test configuration
export let options = {
    stages: [
        { duration: '1m', target: 10 },   // Warm up to 10 users
        { duration: '3m', target: 50 },   // Stay at 50 users
        { duration: '2m', target: 100 },  // Ramp up to 100 users
        { duration: '3m', target: 100 },  // Stay at 100 users
        { duration: '1m', target: 0 },    // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<1000'], // 95% of requests under 1s (accounting for EC2 latency)
        http_req_failed: ['rate<0.1'],     // Error rate under 10%
        errors: ['rate<0.1'],              // Custom error rate under 10%
    },
};

// Service endpoints
const SERVICES = {
    sensor_data: 'http://localhost:3003',
    auth: 'http://localhost:3001',
    gis: 'http://localhost:3007',
    ros: 'http://localhost:3047',
    flow_monitoring: 'http://localhost:3014',
    weather: 'http://localhost:3006',
    water_level: 'http://localhost:3008',
};

// Test data generators
function generateSensorData() {
    return {
        sensor_id: `LOAD_TEST_${Math.floor(Math.random() * 1000)}`,
        type: ['moisture', 'temperature', 'water_level'][Math.floor(Math.random() * 3)],
        value: Math.random() * 100,
        timestamp: new Date().toISOString(),
    };
}

function generateAuthRequest() {
    return {
        username: `user_${Math.floor(Math.random() * 1000)}`,
        password: 'test_password',
    };
}

// Main test scenario
export default function() {
    // Test 1: Sensor Data Ingestion (High frequency)
    group('Sensor Data Service', function() {
        const sensorData = generateSensorData();
        const res = http.post(
            `${SERVICES.sensor_data}/api/v1/telemetry`,
            JSON.stringify(sensorData),
            {
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer test-token'
                },
                timeout: '5s', // Account for EC2 latency
            }
        );
        
        const success = check(res, {
            'sensor data ingestion success': (r) => r.status === 200 || r.status === 201,
            'response time OK': (r) => r.timings.duration < 1000,
        });
        
        errorRate.add(!success);
    });
    
    sleep(0.5); // Simulate realistic user behavior
    
    // Test 2: Query Operations (Medium frequency)
    group('Query Operations', function() {
        // GIS parcel query
        const gisRes = http.get(`${SERVICES.gis}/api/v1/parcels/count`, {
            timeout: '3s',
        });
        
        check(gisRes, {
            'GIS query success': (r) => r.status === 200,
        });
        
        // ROS crop data query
        const rosRes = http.get(`${SERVICES.ros}/api/v1/crops`, {
            timeout: '3s',
        });
        
        check(rosRes, {
            'ROS query success': (r) => r.status === 200,
        });
        
        // Weather data query
        const weatherRes = http.get(`${SERVICES.weather}/api/v1/weather/current`, {
            timeout: '3s',
        });
        
        check(weatherRes, {
            'Weather query success': (r) => r.status === 200,
        });
    });
    
    sleep(1);
    
    // Test 3: Complex Operations (Low frequency)
    if (Math.random() < 0.2) { // 20% of iterations
        group('Complex Operations', function() {
            // Water demand calculation
            const demandReq = {
                plot_id: `PLOT_${Math.floor(Math.random() * 100)}`,
                crop_type: 'RICE',
                growth_stage: 'vegetative',
            };
            
            const demandRes = http.post(
                `${SERVICES.ros}/api/v1/water-demand/calculate`,
                JSON.stringify(demandReq),
                {
                    headers: { 'Content-Type': 'application/json' },
                    timeout: '10s', // Longer timeout for complex calculations
                }
            );
            
            check(demandRes, {
                'water demand calculation success': (r) => r.status === 200,
                'calculation time acceptable': (r) => r.timings.duration < 5000,
            });
            
            // Flow monitoring state check
            const flowRes = http.get(`${SERVICES.flow_monitoring}/api/v1/gates/state`, {
                timeout: '5s',
            });
            
            check(flowRes, {
                'flow monitoring query success': (r) => r.status === 200,
            });
        });
    }
    
    // Test 4: Concurrent Service Access (simulate real usage patterns)
    group('Concurrent Access', function() {
        const batch = http.batch([
            ['GET', `${SERVICES.sensor_data}/api/v1/telemetry/latest`],
            ['GET', `${SERVICES.water_level}/api/v1/levels/current`],
            ['GET', `${SERVICES.gis}/health`],
            ['GET', `${SERVICES.ros}/health`],
        ]);
        
        check(batch[0], {
            'sensor data available': (r) => r.status === 200,
        });
        check(batch[1], {
            'water level available': (r) => r.status === 200,
        });
        check(batch[2], {
            'GIS healthy': (r) => r.status === 200,
        });
        check(batch[3], {
            'ROS healthy': (r) => r.status === 200,
        });
    });
    
    // Random sleep to simulate think time
    sleep(Math.random() * 2 + 1);
}

// Setup function (runs once)
export function setup() {
    console.log('Load test starting...');
    console.log('Testing against EC2 database at 43.209.22.250');
    
    // Verify services are up
    const services = Object.entries(SERVICES);
    let allHealthy = true;
    
    for (const [name, url] of services) {
        try {
            const res = http.get(`${url}/health`, { timeout: '5s' });
            if (res.status !== 200) {
                console.error(`${name} service not healthy: ${res.status}`);
                allHealthy = false;
            }
        } catch (e) {
            console.error(`${name} service not reachable`);
            allHealthy = false;
        }
    }
    
    if (!allHealthy) {
        console.warn('Some services are not healthy, test may have errors');
    }
    
    return { startTime: new Date() };
}

// Teardown function (runs once)
export function teardown(data) {
    console.log('Load test completed');
    console.log(`Duration: ${new Date() - data.startTime}ms`);
}