const fetch = require('node-fetch');

const EC2_HOST = '43.208.201.191';
const API_KEY = 'munbon-internal-f3b89263126548';

async function checkMoistureData() {
    console.log('=== Checking Moisture Sensor Data via API ===');
    console.log('Timestamp:', new Date().toISOString());
    console.log('');

    try {
        // Check health endpoint first
        console.log('1. Checking service health:');
        const healthRes = await fetch(`http://${EC2_HOST}:8080/health`);
        const health = await healthRes.json();
        console.log('Health Status:', JSON.stringify(health, null, 2));
        console.log('');

        // Try to get moisture data from different possible endpoints
        console.log('2. Checking possible moisture endpoints:');
        
        const endpoints = [
            { url: '/api/sensors/moisture', port: 8080 },
            { url: '/api/v1/sensors/moisture/latest', port: 8081 },
            { url: '/api/moisture/latest', port: 3001 },
            { url: '/sensors/moisture', port: 8080 }
        ];

        for (const endpoint of endpoints) {
            try {
                console.log(`\nTrying: http://${EC2_HOST}:${endpoint.port}${endpoint.url}`);
                const res = await fetch(`http://${EC2_HOST}:${endpoint.port}${endpoint.url}`, {
                    headers: {
                        'Content-Type': 'application/json',
                        'x-internal-key': API_KEY
                    },
                    timeout: 5000
                });

                if (res.ok) {
                    const data = await res.json();
                    console.log('Success! Data:', JSON.stringify(data, null, 2));
                } else {
                    console.log(`Status: ${res.status} ${res.statusText}`);
                }
            } catch (err) {
                console.log(`Error: ${err.message}`);
            }
        }

        // Check recent POST requests log
        console.log('\n3. Testing moisture data submission:');
        const testData = {
            gateway_id: "api-test-001",
            gw_id: "api-test-001",
            latitude: 13.7563,
            longitude: 100.5018,
            humid_hi: 55.5,
            humid_low: 48.2,
            temp_hi: 29.3,
            temp_low: 27.1,
            timestamp: new Date().toISOString()
        };

        const postRes = await fetch(`http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(testData)
        });

        const postResult = await postRes.json();
        console.log('Test submission result:', postResult);

    } catch (error) {
        console.error('Error:', error.message);
    }
}

checkMoistureData();