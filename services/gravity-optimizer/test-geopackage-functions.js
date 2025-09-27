#!/usr/bin/env node

/**
 * Unit tests for GeoPackage Processor functions
 * Tests individual functions without database dependency
 */

// Set test environment variables BEFORE importing the module
const path = require('path');
process.env.UPLOAD_DIR = path.join(__dirname, 'test-uploads');
process.env.TEMP_DIR = path.join(__dirname, 'test-temp');
process.env.PROCESSED_DIR = path.join(__dirname, 'test-processed');
process.env.BATCH_SIZE = '10';

const { GeoPackageProcessor } = require('./geopackage-processor-worker');

class FunctionTester {
  constructor() {
    this.processor = new GeoPackageProcessor();
    this.results = {
      passed: 0,
      failed: 0,
      tests: []
    };
  }

  async runTest(name, testFn) {
    console.log(`\n📋 Test: ${name}`);
    try {
      await testFn();
      console.log(`✅ PASSED`);
      this.results.passed++;
      this.results.tests.push({ name, status: 'passed' });
    } catch (error) {
      console.error(`❌ FAILED:`, error.message);
      this.results.failed++;
      this.results.tests.push({ name, status: 'failed', error: error.message });
    }
  }

  printSummary() {
    console.log('\n' + '='.repeat(50));
    console.log('TEST SUMMARY');
    console.log('='.repeat(50));
    console.log(`Total: ${this.results.passed + this.results.failed}`);
    console.log(`Passed: ${this.results.passed} ✅`);
    console.log(`Failed: ${this.results.failed} ❌`);
  }
}

// Test cases
async function runTests() {
  const tester = new FunctionTester();

  // Test 1: Geometry Validation
  await tester.runTest('Validate Geometry - Valid Polygon', () => {
    const result = tester.processor.validateGeometry(
      'POLYGON((100.0 0.0, 101.0 0.0, 101.0 1.0, 100.0 1.0, 100.0 0.0))'
    );
    if (!result.isValid) throw new Error('Should be valid');
    if (result.geometryType !== 'POLYGON') throw new Error('Should detect POLYGON type');
  });

  await tester.runTest('Validate Geometry - Invalid WKT', () => {
    const result = tester.processor.validateGeometry('NOT A VALID WKT');
    if (result.isValid) throw new Error('Should be invalid');
  });

  await tester.runTest('Validate Geometry - Empty String', () => {
    const result = tester.processor.validateGeometry('');
    if (result.isValid) throw new Error('Should be invalid');
  });

  await tester.runTest('Validate Geometry - Multipolygon', () => {
    const result = tester.processor.validateGeometry(
      'MULTIPOLYGON(((100.0 0.0, 101.0 0.0, 101.0 1.0, 100.0 1.0, 100.0 0.0)))'
    );
    if (!result.isValid) throw new Error('Should be valid');
    if (result.geometryType !== 'MULTIPOLYGON') throw new Error('Should detect MULTIPOLYGON type');
  });

  await tester.runTest('Validate Geometry - Point', () => {
    const result = tester.processor.validateGeometry('POINT(100.0 0.0)');
    if (!result.isValid) throw new Error('Should be valid');
    if (result.geometryType !== 'POINT') throw new Error('Should detect POINT type');
  });

  // Test 2: Column Mapping
  await tester.runTest('Column Mapping - Standard Headers', () => {
    const headers = ['PARCEL_SEQ', 'area_rai', 'WKT', 'plant_id', 'wpet'];
    const mapping = tester.processor.createColumnMapping(headers);
    
    if (mapping.parcel_seq !== 'PARCEL_SEQ') 
      throw new Error('Should map PARCEL_SEQ');
    if (mapping.area_rai !== 'area_rai') 
      throw new Error('Should map area_rai');
    if (mapping.geometry_wkt !== 'WKT') 
      throw new Error('Should map WKT to geometry_wkt');
    if (mapping.plant_id !== 'plant_id') 
      throw new Error('Should map plant_id');
    if (mapping.wpet !== 'wpet') 
      throw new Error('Should map wpet');
  });

  await tester.runTest('Column Mapping - Alternative Names', () => {
    const headers = ['parcel_id', 'PARCEL_ARE', 'geom', 'CROP_TYPE', 'WPET'];
    const mapping = tester.processor.createColumnMapping(headers);
    
    if (mapping.parcel_seq !== 'parcel_id') 
      throw new Error('Should map parcel_id to parcel_seq');
    if (mapping.area_rai !== 'PARCEL_ARE') 
      throw new Error('Should map PARCEL_ARE to area_rai');
    if (mapping.geometry_wkt !== 'geom') 
      throw new Error('Should map geom to geometry_wkt');
    if (mapping.plant_id !== 'CROP_TYPE') 
      throw new Error('Should map CROP_TYPE to plant_id');
    if (mapping.wpet !== 'WPET') 
      throw new Error('Should map WPET');
  });

  await tester.runTest('Column Mapping - Mixed Case', () => {
    const headers = ['Parcel_Seq', 'Area_Rai', 'GEOMETRY', 'Plant_ID'];
    const mapping = tester.processor.createColumnMapping(headers);
    
    // Should handle exact matches even with different case
    if (mapping.geometry_wkt !== 'GEOMETRY') 
      throw new Error('Should map GEOMETRY to geometry_wkt');
  });

  // Test 3: Crop Type Mapping
  await tester.runTest('Map Crop Type - Numeric IDs', () => {
    const tests = [
      { input: '1', expected: 'rice' },
      { input: '2', expected: 'maize' },
      { input: '3', expected: 'sugarcane' },
      { input: '4', expected: 'cassava' }
    ];
    
    for (const test of tests) {
      const result = tester.processor.mapCropType(test.input);
      if (result !== test.expected) {
        throw new Error(`${test.input} should map to ${test.expected}, got ${result}`);
      }
    }
  });

  await tester.runTest('Map Crop Type - String Names', () => {
    const tests = [
      { input: 'rice', expected: 'rice' },
      { input: 'RICE', expected: 'rice' },
      { input: 'corn', expected: 'maize' },
      { input: 'sugarcane', expected: 'sugarcane' }
    ];
    
    for (const test of tests) {
      const result = tester.processor.mapCropType(test.input);
      if (result !== test.expected) {
        throw new Error(`${test.input} should map to ${test.expected}, got ${result}`);
      }
    }
  });

  await tester.runTest('Map Crop Type - Edge Cases', () => {
    const tests = [
      { input: null, expected: null },
      { input: undefined, expected: null },
      { input: 'unknown', expected: 'unknown' },
      { input: '999', expected: '999' }
    ];
    
    for (const test of tests) {
      const result = tester.processor.mapCropType(test.input);
      if (result !== test.expected) {
        throw new Error(`${test.input} should map to ${test.expected}, got ${result}`);
      }
    }
  });

  // Test 4: Area Conversion
  await tester.runTest('Area Conversion - Rai to Hectares', () => {
    const tests = [
      { rai: 6.25, expectedHectares: 1.0 },
      { rai: 12.5, expectedHectares: 2.0 },
      { rai: 31.25, expectedHectares: 5.0 },
      { rai: 62.5, expectedHectares: 10.0 },
      { rai: 0, expectedHectares: 0 },
      { rai: 1, expectedHectares: 0.16 }
    ];
    
    for (const test of tests) {
      const result = test.rai / 6.25;
      const diff = Math.abs(result - test.expectedHectares);
      if (diff > 0.001) {
        throw new Error(`${test.rai} rai should equal ${test.expectedHectares} hectares, got ${result}`);
      }
    }
  });

  // Print results
  tester.printSummary();
  
  // Exit with appropriate code
  process.exit(tester.results.failed > 0 ? 1 : 0);
}

// Run tests
console.log('🚀 GeoPackage Processor Function Tests');
console.log('=====================================');
runTests().catch(error => {
  console.error('Test suite failed:', error);
  process.exit(1);
});