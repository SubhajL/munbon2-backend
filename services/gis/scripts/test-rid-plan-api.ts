#!/usr/bin/env ts-node

import axios from 'axios';
import { logger } from '../src/utils/logger';

const API_BASE = 'http://localhost:3007/api/v1';
const TOKEN = process.env.JWT_TOKEN || 'your-jwt-token-here';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Authorization': `Bearer ${TOKEN}`,
    'Content-Type': 'application/json'
  }
});

async function testRidPlanEndpoints() {
  console.log('Testing RID Plan API Endpoints...\n');

  try {
    // Test 1: Get parcels with pagination
    console.log('1. Testing GET /rid-plan/parcels');
    const parcelsResponse = await api.get('/rid-plan/parcels', {
      params: { limit: 5, page: 1 }
    });
    console.log(`   ✓ Found ${parcelsResponse.data.pagination.total} total parcels`);
    console.log(`   ✓ Retrieved ${parcelsResponse.data.features.length} parcels in page 1`);

    // Test 2: Get specific parcel
    if (parcelsResponse.data.features.length > 0) {
      const firstParcelId = parcelsResponse.data.features[0].properties.id;
      console.log('\n2. Testing GET /rid-plan/parcels/:id');
      const parcelResponse = await api.get(`/rid-plan/parcels/${firstParcelId}`);
      console.log(`   ✓ Retrieved parcel: ${parcelResponse.data.properties.plotCode}`);
      console.log(`   ✓ Area: ${parcelResponse.data.properties.areaRai} rai`);
    }

    // Test 3: Get statistics
    console.log('\n3. Testing GET /rid-plan/statistics');
    const statsResponse = await api.get('/rid-plan/statistics');
    console.log(`   ✓ Total parcels: ${statsResponse.data.summary.total_parcels}`);
    console.log(`   ✓ Total area: ${statsResponse.data.summary.total_area_rai} rai`);
    console.log(`   ✓ Statistics grouped by: ${statsResponse.data.groupedBy}`);
    console.log(`   ✓ Number of groups: ${statsResponse.data.statistics.length}`);

    // Test 4: Search locations
    console.log('\n4. Testing GET /rid-plan/search');
    const searchResponse = await api.get('/rid-plan/search', {
      params: { q: 'นคร', type: 'both' }
    });
    console.log(`   ✓ Found ${searchResponse.data.results.length} locations matching 'นคร'`);

    // Test 5: Water demand analysis
    console.log('\n5. Testing GET /rid-plan/water-demand');
    const waterResponse = await api.get('/rid-plan/water-demand');
    console.log(`   ✓ Total water demand: ${(waterResponse.data.summary.totalWaterDemandM3 / 1000000).toFixed(2)} million m³`);
    console.log(`   ✓ Average per rai: ${waterResponse.data.summary.waterDemandPerRai.toFixed(0)} m³`);

    // Test 6: Filter by amphoe
    console.log('\n6. Testing filters');
    if (statsResponse.data.statistics.length > 0) {
      const firstAmphoe = statsResponse.data.statistics[0].amphoe;
      const filteredResponse = await api.get('/rid-plan/parcels', {
        params: { amphoe: firstAmphoe, limit: 10 }
      });
      console.log(`   ✓ Filtered by amphoe '${firstAmphoe}': ${filteredResponse.data.features.length} results`);
    }

    // Test 7: Spatial query with bbox
    console.log('\n7. Testing spatial query');
    const bboxResponse = await api.get('/rid-plan/parcels', {
      params: { 
        bbox: '102,14.5,103,15.5',
        limit: 10 
      }
    });
    console.log(`   ✓ Spatial query returned ${bboxResponse.data.features.length} parcels`);

    console.log('\n✅ All tests passed successfully!');

  } catch (error: any) {
    console.error('\n❌ Test failed:', error.message);
    if (error.response) {
      console.error('Response:', error.response.data);
      console.error('Status:', error.response.status);
    }
  }
}

// Run tests
testRidPlanEndpoints();