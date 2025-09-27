const { GeoPackageTestExtractor } = require('../dist/services/geopackage-test-extractor');
const fs = require('fs');
const path = require('path');

// Set up basic logger if not available
if (!global.logger) {
    global.logger = {
        info: console.log,
        warn: console.warn,
        error: console.error,
        debug: console.debug
    };
}

async function runTests() {
    const extractor = new GeoPackageTestExtractor();
    
    console.log('=== GeoPackage API Test Suite ===\n');
    
    // Test 1: Test with a sample file
    const testFile = process.argv[2];
    
    if (!testFile) {
        console.error('Usage: node test-geopackage-extraction.js <path-to-gpkg-file>');
        process.exit(1);
    }
    
    console.log(`Testing with file: ${testFile}`);
    
    try {
        const results = await extractor.testExtractGeoPackage(testFile);
        
        console.log('\n=== Test Results ===');
        console.log(`File: ${results.filePath}`);
        console.log(`Tables found: ${results.tables.length}`);
        console.log(`GeoPackage API methods: ${results.apiMethods.geoPackage?.length || 0}`);
        
        // Print table details
        for (const table of results.tables) {
            console.log(`\n--- Table: ${table.tableName} ---`);
            console.log(`Columns: ${table.columns.length}`);
            console.log(`Rows: ${table.rowCount}`);
            console.log(`SRS: ${JSON.stringify(table.srs)}`);
            console.log(`DAO Methods: ${table.daoMethods.length}`);
            
            if (table.columns.length > 0) {
                console.log('\nColumn Details:');
                table.columns.slice(0, 10).forEach(col => {
                    console.log(`  - ${col.name} (${col.type})${col.isPrimary ? ' [PRIMARY]' : ''}`);
                });
            }
            
            if (table.sampleRows.length > 0) {
                console.log(`\nSample Data (${table.sampleRows.length} rows):`);
                console.log('First row properties:', Object.keys(table.sampleRows[0].properties));
            }
        }
        
        if (results.errors.length > 0) {
            console.log('\n=== Errors ===');
            results.errors.forEach(err => console.error(err));
        }
        
    } catch (error) {
        console.error('Test failed:', error);
        process.exit(1);
    }
}

// Run the tests
runTests();