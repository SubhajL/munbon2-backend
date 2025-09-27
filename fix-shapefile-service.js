// Quick fix for shapefile.service.js to handle new processor response format

const fs = require('fs');
const path = require('path');

const filePath = '/home/ubuntu/munbon2-backend/services/gis/dist/services/shapefile.service.js';

// Read the file
const content = fs.readFileSync(filePath, 'utf8');

// Replace the problematic section
const updatedContent = content.replace(
    `const parcels = await this.processor.processShapeFile({
                    buffer: s3Object.Body,
                    fileName,
                    uploadId,
                });
                await this.storeParcels(uploadId, parcels);
                await this.updateUploadStatus(uploadId, 'completed', {
                    parcelCount: parcels.length,
                    completedAt: new Date(),
                });
                logger_1.logger.info('Shape file processing completed', { uploadId, parcelCount: parcels.length });`,
    `const result = await this.processor.processShapeFile({
                    buffer: s3Object.Body,
                    fileName,
                    uploadId,
                });
                // Handle both old format (array) and new format (object with parcels property)
                const parcels = Array.isArray(result) ? result : (result.parcels || []);
                const parcelCount = parcels.length;
                
                await this.storeParcels(uploadId, parcels);
                await this.updateUploadStatus(uploadId, 'completed', {
                    parcelCount: parcelCount,
                    completedAt: new Date(),
                });
                logger_1.logger.info('Shape file processing completed', { uploadId, parcelCount: parcelCount });`
);

// Write the updated content back
fs.writeFileSync(filePath, updatedContent);

console.log('Fixed shapefile.service.js to handle new processor response format');