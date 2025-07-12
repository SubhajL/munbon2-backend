require('dotenv').config();
const AWS = require('aws-sdk');
const fs = require('fs');
const AdmZip = require('adm-zip');
const shapefile = require('shapefile');
const { promisify } = require('util');
const writeFile = promisify(fs.writeFile);

AWS.config.update({ region: 'ap-southeast-1' });
const s3 = new AWS.S3();

async function checkShapefileFields() {
  try {
    // Download the shapefile from S3
    const params = {
      Bucket: 'munbon-gis-shape-files',
      Key: 'shape-files/2025-07-04/4db50588-1762-4830-b09f-ae5e2ab4dbf9/ridplan_rice_20250702.zip'
    };
    
    console.log('Downloading shapefile from S3...');
    const data = await s3.getObject(params).promise();
    
    // Save to temporary file
    const tempZipPath = '/tmp/test-shapefile.zip';
    await writeFile(tempZipPath, data.Body);
    
    // Extract zip
    console.log('Extracting shapefile...');
    const extractDir = '/tmp/shapefile-extract';
    const zip = new AdmZip(tempZipPath);
    zip.extractAllTo(extractDir, true);
    
    // Find .shp file
    const files = fs.readdirSync(extractDir);
    const shpFile = files.find(f => f.endsWith('.shp'));
    
    if (!shpFile) {
      throw new Error('No .shp file found in archive');
    }
    
    const shpPath = `${extractDir}/${shpFile}`;
    console.log(`\nReading shapefile: ${shpFile}`);
    
    // Read first few features to examine fields
    const source = await shapefile.open(shpPath);
    let count = 0;
    let result;
    let sampleProperties = null;
    
    while (!(result = await source.read()).done && count < 3) {
      const feature = result.value;
      
      if (count === 0) {
        console.log('\nAvailable fields in shapefile:');
        console.log('==============================');
        const properties = feature.properties;
        Object.keys(properties).forEach(key => {
          const value = properties[key];
          const type = typeof value;
          console.log(`- ${key}: ${type} (sample: ${JSON.stringify(value)})`);
        });
        sampleProperties = properties;
      }
      
      count++;
    }
    
    // Check specific RID fields
    console.log('\n\nRID Fields Analysis:');
    console.log('====================');
    
    const ridFields = {
      'PARCEL_SEQ': 'Parcel reference ID',
      'sub_member': 'Zone number (1-6)',
      'parcel_area_rai': 'Parcel area in rai',
      'data_date_process': 'Data processing date',
      'start_int': 'Planting start date',
      'wpet': 'Water productivity (ET)',
      'age': 'Plant age',
      'wprod': 'Water productivity',
      'plant_id': 'Plant/crop type ID',
      'yield_at_mc_kgpr': 'Yield (kg/rai)',
      'season_irr_m3_per_rai': 'Seasonal water demand (m³/rai)',
      'auto_note': 'Irrigation dates (JSON)'
    };
    
    for (const [field, description] of Object.entries(ridFields)) {
      if (sampleProperties && field in sampleProperties) {
        console.log(`✓ ${field}: ${description}`);
        console.log(`  Sample value: ${JSON.stringify(sampleProperties[field])}`);
      } else {
        console.log(`✗ ${field}: Not found`);
      }
    }
    
    // Check for water level and crop height
    console.log('\n\nAdditional Fields Check:');
    console.log('========================');
    
    const additionalFields = ['water_level', 'crop_height', 'moisture', 'water_depth'];
    additionalFields.forEach(field => {
      if (sampleProperties && field in sampleProperties) {
        console.log(`✓ ${field}: Found (value: ${sampleProperties[field]})`);
      } else {
        console.log(`✗ ${field}: Not found in shapefile`);
      }
    });
    
    // Cleanup
    fs.rmSync(tempZipPath, { force: true });
    fs.rmSync(extractDir, { recursive: true, force: true });
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

checkShapefileFields();