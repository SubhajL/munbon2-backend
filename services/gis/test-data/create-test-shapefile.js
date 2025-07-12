const fs = require('fs');
const AdmZip = require('adm-zip');
const path = require('path');

// Create a simple test shapefile structure
const testDir = path.join(__dirname, 'test-shape');
if (!fs.existsSync(testDir)) {
  fs.mkdirSync(testDir, { recursive: true });
}

// Create a minimal .shp file header (this is a dummy file for testing)
const shpBuffer = Buffer.alloc(100);
shpBuffer.writeInt32BE(9994, 0); // File code
shpBuffer.writeInt32BE(100, 24); // File length
shpBuffer.writeInt32LE(1000, 28); // Version
shpBuffer.writeInt32LE(5, 32); // Shape type (polygon)

fs.writeFileSync(path.join(testDir, 'test.shp'), shpBuffer);

// Create a .dbf file with some attributes
const dbfContent = `ID,ZONE,OWNER,AREA
1,Zone1,John Doe,1000.5
2,Zone1,Jane Smith,1500.2
3,Zone2,Bob Johnson,2000.7`;

fs.writeFileSync(path.join(testDir, 'test.dbf'), dbfContent);

// Create a .prj file with WGS84 projection
const prjContent = `GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]`;
fs.writeFileSync(path.join(testDir, 'test.prj'), prjContent);

// Create a .shx file (index)
const shxBuffer = Buffer.alloc(100);
fs.writeFileSync(path.join(testDir, 'test.shx'), shxBuffer);

// Create the zip file
const zip = new AdmZip();
zip.addLocalFolder(testDir);
zip.writeZip(path.join(__dirname, 'test-shapefile.zip'));

console.log('Test shapefile created: test-shapefile.zip');

// Clean up
fs.rmSync(testDir, { recursive: true, force: true });