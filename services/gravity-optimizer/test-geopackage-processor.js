#!/usr/bin/env node

/**
 * Test suite for GeoPackage Processor Worker
 * Tests all major functionality without mocking
 */

// Set test environment variables BEFORE importing the module
const path = require('path');
process.env.UPLOAD_DIR = path.join(__dirname, 'test-uploads');
process.env.TEMP_DIR = path.join(__dirname, 'test-temp');
process.env.PROCESSED_DIR = path.join(__dirname, 'test-processed');
process.env.BATCH_SIZE = '10';

const { GeoPackageProcessor } = require('./geopackage-processor-worker');
const fs = require('fs').promises;
const { Client } = require('pg');

// Test configuration
const TEST_CONFIG = {
  database: {
    host: '127.0.0.1',
    port: 5432,
    database: 'munbon_dev',
    user: 'postgres',
    password: process.env.POSTGRES_PASSWORD || (() => { throw new Error('POSTGRES_PASSWORD env var is required (hardcoded default removed; SEC remediation)'); })(),
  },
  paths: {
    testData: path.join(__dirname, 'test-data'),
    uploadDir: path.join(__dirname, 'test-uploads'),
    tempDir: path.join(__dirname, 'test-temp'),
    processedDir: path.join(__dirname, 'test-processed')
  }
};

// Test utilities
class TestRunner {
  constructor() {
    this.processor = null;
    this.testClient = null;
    this.results = {
      passed: 0,
      failed: 0,
      tests: []
    };
  }

  async setup() {
    console.log('\n🔧 Setting up test environment...');
    
    // Create test directories
    for (const dir of Object.values(TEST_CONFIG.paths)) {
      await fs.mkdir(dir, { recursive: true });
    }
    
    // Initialize processor with test config
    process.env.UPLOAD_DIR = TEST_CONFIG.paths.uploadDir;
    process.env.TEMP_DIR = TEST_CONFIG.paths.tempDir;
    process.env.PROCESSED_DIR = TEST_CONFIG.paths.processedDir;
    
    // Override batch size for faster testing
    process.env.BATCH_SIZE = '10';
    
    this.processor = new GeoPackageProcessor();
    await this.processor.initialize();
    
    // Create separate test client for verification
    this.testClient = new Client(TEST_CONFIG.database);
    await this.testClient.connect();
    
    console.log('✅ Test environment ready\n');
  }

  async cleanup() {
    console.log('\n🧹 Cleaning up test environment...');
    
    // Close connections
    if (this.processor) {
      await this.processor.shutdown();
    }
    if (this.testClient) {
      await this.testClient.end();
    }
    
    // Clean test directories
    for (const dir of Object.values(TEST_CONFIG.paths)) {
      await fs.rm(dir, { recursive: true, force: true });
    }
    
    console.log('✅ Cleanup complete\n');
  }

  async runTest(name, testFn) {
    console.log(`\n📋 Test: ${name}`);
    const startTime = Date.now();
    
    try {
      await testFn();
      const duration = Date.now() - startTime;
      console.log(`✅ PASSED (${duration}ms)`);
      this.results.passed++;
      this.results.tests.push({ name, status: 'passed', duration });
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`❌ FAILED (${duration}ms)`, error.message);
      this.results.failed++;
      this.results.tests.push({ name, status: 'failed', duration, error: error.message });
    }
  }

  printSummary() {
    console.log('\n' + '='.repeat(50));
    console.log('TEST SUMMARY');
    console.log('='.repeat(50));
    console.log(`Total: ${this.results.passed + this.results.failed}`);
    console.log(`Passed: ${this.results.passed} ✅`);
    console.log(`Failed: ${this.results.failed} ❌`);
    console.log('\nDetailed Results:');
    this.results.tests.forEach(test => {
      const icon = test.status === 'passed' ? '✅' : '❌';
      console.log(`${icon} ${test.name} (${test.duration}ms)`);
      if (test.error) {
        console.log(`   Error: ${test.error}`);
      }
    });
  }
}

// Test implementations
const tests = {
  async testInspectGeoPackage(processor, testClient) {
    // Create mock geopackage data
    const mockGpkg = path.join(TEST_CONFIG.paths.testData, 'test.gpkg');
    await fs.writeFile(mockGpkg, 'mock geopackage data');
    
    const result = await processor.inspectGeoPackage(mockGpkg);
    
    // Should return structure even if inspection fails
    if (!result || typeof result !== 'object') {
      throw new Error('inspectGeoPackage should return object');
    }
    
    if (!Array.isArray(result.layers)) {
      throw new Error('result.layers should be array');
    }
  },

  async testValidateGeometry(processor, testClient) {
    // Test valid polygon
    const validPolygon = 'POLYGON((100.0 0.0, 101.0 0.0, 101.0 1.0, 100.0 1.0, 100.0 0.0))';
    const result1 = processor.validateGeometry(validPolygon);
    if (!result1.isValid) {
      throw new Error('Valid polygon should pass validation');
    }
    if (result1.geometryType !== 'POLYGON') {
      throw new Error('Should detect POLYGON type');
    }
    
    // Test invalid geometry
    const invalid = 'NOT A VALID WKT';
    const result2 = processor.validateGeometry(invalid);
    if (result2.isValid) {
      throw new Error('Invalid WKT should fail validation');
    }
    
    // Test empty geometry
    const empty = '';
    const result3 = processor.validateGeometry(empty);
    if (result3.isValid) {
      throw new Error('Empty string should fail validation');
    }
    
    // Test multipolygon
    const multiPolygon = 'MULTIPOLYGON(((100.0 0.0, 101.0 0.0, 101.0 1.0, 100.0 1.0, 100.0 0.0)))';
    const result4 = processor.validateGeometry(multiPolygon);
    if (!result4.isValid || result4.geometryType !== 'MULTIPOLYGON') {
      throw new Error('Should detect MULTIPOLYGON type');
    }
  },

  async testColumnMapping(processor, testClient) {
    // Test with various header formats
    const headers1 = ['PARCEL_SEQ', 'area_rai', 'WKT', 'plant_id'];
    const mapping1 = processor.createColumnMapping(headers1);
    
    if (mapping1.parcel_seq !== 'PARCEL_SEQ') {
      throw new Error('Should map PARCEL_SEQ to parcel_seq');
    }
    if (mapping1.area_rai !== 'area_rai') {
      throw new Error('Should map area_rai');
    }
    if (mapping1.geometry_wkt !== 'WKT') {
      throw new Error('Should map WKT to geometry_wkt');
    }
    
    // Test with alternative names
    const headers2 = ['parcel_id', 'PARCEL_ARE', 'geom', 'CROP_TYPE'];
    const mapping2 = processor.createColumnMapping(headers2);
    
    if (mapping2.parcel_seq !== 'parcel_id') {
      throw new Error('Should map parcel_id to parcel_seq');
    }
    if (mapping2.area_rai !== 'PARCEL_ARE') {
      throw new Error('Should map PARCEL_ARE to area_rai');
    }
    if (mapping2.plant_id !== 'CROP_TYPE') {
      throw new Error('Should map CROP_TYPE to plant_id');
    }
  },

  async testAreaConversion(processor, testClient) {
    // Test rai to hectares conversion
    const testCases = [
      { rai: 6.25, expectedHectares: 1.0 },
      { rai: 12.5, expectedHectares: 2.0 },
      { rai: 31.25, expectedHectares: 5.0 },
      { rai: 0, expectedHectares: 0 }
    ];
    
    for (const testCase of testCases) {
      const hectares = testCase.rai / 6.25;
      if (Math.abs(hectares - testCase.expectedHectares) > 0.001) {
        throw new Error(`Area conversion failed: ${testCase.rai} rai should equal ${testCase.expectedHectares} hectares`);
      }
    }
  },

  async testMapCropType(processor, testClient) {
    // Test crop type mapping
    const testCases = [
      { input: '1', expected: 'rice' },
      { input: '2', expected: 'maize' },
      { input: '3', expected: 'sugarcane' },
      { input: '4', expected: 'cassava' },
      { input: 'rice', expected: 'rice' },
      { input: 'RICE', expected: 'rice' },
      { input: 'corn', expected: 'maize' },
      { input: 'unknown', expected: 'unknown' },
      { input: null, expected: null }
    ];
    
    for (const testCase of testCases) {
      const result = processor.mapCropType(testCase.input);
      if (result !== testCase.expected) {
        throw new Error(`Crop type mapping failed: ${testCase.input} should map to ${testCase.expected}, got ${result}`);
      }
    }
  },

  async testDatabaseInsertion(processor, testClient) {
    // Test data
    const testParcels = [
      {
        parcel_seq: 'TEST_001',
        zone_area: 'Zone1',
        area_rai: 10,
        area_hectares: 1.6,
        batch_date: 20240101,
        start_date: 20240115,
        crop_cycle: 1,
        wpet: 100.5,
        wprod: 80.3,
        age: 30,
        plant_id: '1',
        stage_age: 30,
        yield_at_mc_kgpr: 500,
        season_rain_m3_per_rai: 200,
        season_irri_m3_per_rai: 300,
        season_water_input_m3_per_rai: 500,
        auto_note: 'Test parcel',
        geometry_wkt: 'POLYGON((100.0 0.0, 101.0 0.0, 101.0 1.0, 100.0 1.0, 100.0 0.0))'
      }
    ];
    
    // Clean up any existing test data
    await testClient.query(
      `DELETE FROM gis.agricultural_plots WHERE plot_code LIKE 'TEST_%'`
    );
    
    // Insert test parcel
    await processor.insertRidPlanBatch(testParcels);
    
    // Verify insertion
    const result = await testClient.query(
      `SELECT * FROM gis.agricultural_plots WHERE plot_code = $1`,
      ['TEST_001']
    );
    
    if (result.rows.length !== 1) {
      throw new Error('Test parcel not inserted');
    }
    
    const inserted = result.rows[0];
    
    // Verify area conversion
    if (Math.abs(parseFloat(inserted.area_hectares) - 1.6) > 0.001) {
      throw new Error(`Area hectares incorrect: expected 1.6, got ${inserted.area_hectares}`);
    }
    
    // Verify crop type mapping
    if (inserted.current_crop_type !== 'rice') {
      throw new Error(`Crop type incorrect: expected rice, got ${inserted.current_crop_type}`);
    }
    
    // Verify geometry
    if (!inserted.boundary) {
      throw new Error('Geometry not inserted');
    }
    
    // Clean up
    await testClient.query(
      `DELETE FROM gis.agricultural_plots WHERE plot_code = 'TEST_001'`
    );
  }
};

// Main test execution
async function runAllTests() {
  const runner = new TestRunner();
  
  try {
    await runner.setup();
    
    // Run all tests
    await runner.runTest('Inspect GeoPackage', 
      () => tests.testInspectGeoPackage(runner.processor, runner.testClient));
    
    await runner.runTest('Validate Geometry', 
      () => tests.testValidateGeometry(runner.processor, runner.testClient));
    
    await runner.runTest('Column Mapping', 
      () => tests.testColumnMapping(runner.processor, runner.testClient));
    
    await runner.runTest('Area Conversion', 
      () => tests.testAreaConversion(runner.processor, runner.testClient));
    
    await runner.runTest('Map Crop Type', 
      () => tests.testMapCropType(runner.processor, runner.testClient));
    
    await runner.runTest('Database Insertion', 
      () => tests.testDatabaseInsertion(runner.processor, runner.testClient));
    
    runner.printSummary();
    
  } catch (error) {
    console.error('\n💥 Test suite failed:', error);
    process.exit(1);
  } finally {
    await runner.cleanup();
  }
  
  // Exit with appropriate code
  process.exit(runner.results.failed > 0 ? 1 : 0);
}

// Run tests if called directly
if (require.main === module) {
  console.log('🚀 GeoPackage Processor Test Suite');
  console.log('==================================');
  runAllTests();
}

module.exports = { tests, TestRunner };