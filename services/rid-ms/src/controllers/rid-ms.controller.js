"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.RidMsController = void 0;
const aws_sdk_1 = __importDefault(require("aws-sdk"));
const logger_1 = require("../utils/logger");
const dynamodb = new aws_sdk_1.default.DynamoDB.DocumentClient({
    region: process.env.AWS_REGION || 'ap-southeast-1',
});
const s3 = new aws_sdk_1.default.S3({
    region: process.env.AWS_REGION || 'ap-southeast-1',
});
const SHAPE_FILE_TABLE = process.env.SHAPE_FILE_TABLE || 'rid-ms-shapefiles-dev';
const PARCEL_TABLE = process.env.PARCEL_TABLE || 'rid-ms-parcels-dev';
const WATER_DEMAND_TABLE = process.env.WATER_DEMAND_TABLE || 'rid-ms-water-demand-dev';
const PROCESSED_BUCKET = process.env.PROCESSED_BUCKET || 'rid-ms-processed-dev';
class RidMsController {
    async getShapeFiles(req, res) {
        try {
            const { status, limit = 20, lastKey } = req.query;
            const params = {
                TableName: SHAPE_FILE_TABLE,
                Limit: Number(limit),
            };
            if (status) {
                params.IndexName = 'status-uploadTime-index';
                params.KeyConditionExpression = '#status = :status';
                params.ExpressionAttributeNames = { '#status': 'status' };
                params.ExpressionAttributeValues = { ':status': status };
            }
            if (lastKey) {
                params.ExclusiveStartKey = JSON.parse(lastKey);
            }
            const result = await dynamodb.query(params).promise();
            res.json({
                items: result.Items,
                lastKey: result.LastEvaluatedKey,
                count: result.Items?.length || 0,
            });
        }
        catch (error) {
            logger_1.logger.error('Error fetching shape files:', error);
            res.status(500).json({ error: 'Failed to fetch shape files' });
        }
    }
    async getShapeFileById(req, res) {
        try {
            const { id } = req.params;
            const result = await dynamodb.get({
                TableName: SHAPE_FILE_TABLE,
                Key: { id },
            }).promise();
            if (!result.Item) {
                return res.status(404).json({ error: 'Shape file not found' });
            }
            res.json(result.Item);
        }
        catch (error) {
            logger_1.logger.error('Error fetching shape file:', error);
            res.status(500).json({ error: 'Failed to fetch shape file' });
        }
    }
    async getParcelsByShapeFile(req, res) {
        try {
            const { shapeFileId } = req.params;
            const { limit = 100, lastKey } = req.query;
            const params = {
                TableName: PARCEL_TABLE,
                IndexName: 'shapeFileId-index',
                KeyConditionExpression: 'shapeFileId = :shapeFileId',
                ExpressionAttributeValues: {
                    ':shapeFileId': shapeFileId,
                },
                Limit: Number(limit),
            };
            if (lastKey) {
                params.ExclusiveStartKey = JSON.parse(lastKey);
            }
            const result = await dynamodb.query(params).promise();
            res.json({
                items: result.Items,
                lastKey: result.LastEvaluatedKey,
                count: result.Items?.length || 0,
            });
        }
        catch (error) {
            logger_1.logger.error('Error fetching parcels:', error);
            res.status(500).json({ error: 'Failed to fetch parcels' });
        }
    }
    async getParcelsByZone(req, res) {
        try {
            const { zone } = req.params;
            const { waterDemandMethod, limit = 100, lastKey } = req.query;
            const params = {
                TableName: PARCEL_TABLE,
                IndexName: 'zone-index',
                KeyConditionExpression: 'zone = :zone',
                ExpressionAttributeValues: {
                    ':zone': zone,
                },
                Limit: Number(limit),
            };
            if (waterDemandMethod) {
                params.FilterExpression = 'waterDemandMethod = :method';
                params.ExpressionAttributeValues[':method'] = waterDemandMethod;
            }
            if (lastKey) {
                params.ExclusiveStartKey = JSON.parse(lastKey);
            }
            const result = await dynamodb.query(params).promise();
            res.json({
                items: result.Items,
                lastKey: result.LastEvaluatedKey,
                count: result.Items?.length || 0,
            });
        }
        catch (error) {
            logger_1.logger.error('Error fetching parcels by zone:', error);
            res.status(500).json({ error: 'Failed to fetch parcels' });
        }
    }
    async getParcelWaterDemand(req, res) {
        try {
            const { parcelId } = req.params;
            const result = await dynamodb.query({
                TableName: WATER_DEMAND_TABLE,
                KeyConditionExpression: 'parcelId = :parcelId',
                ExpressionAttributeValues: {
                    ':parcelId': parcelId,
                },
                ScanIndexForward: false,
                Limit: 1,
            }).promise();
            if (!result.Items || result.Items.length === 0) {
                return res.status(404).json({ error: 'Water demand not found' });
            }
            res.json(result.Items[0]);
        }
        catch (error) {
            logger_1.logger.error('Error fetching water demand:', error);
            res.status(500).json({ error: 'Failed to fetch water demand' });
        }
    }
    async getWaterDemandSummaryByZone(req, res) {
        try {
            const { zone } = req.params;
            const parcelsResult = await dynamodb.query({
                TableName: PARCEL_TABLE,
                IndexName: 'zone-index',
                KeyConditionExpression: 'zone = :zone',
                ExpressionAttributeValues: {
                    ':zone': zone,
                },
            }).promise();
            if (!parcelsResult.Items || parcelsResult.Items.length === 0) {
                return res.json({
                    zone,
                    parcelCount: 0,
                    totalArea: 0,
                    waterDemandSummary: {},
                });
            }
            const waterDemandPromises = parcelsResult.Items.map(parcel => dynamodb.query({
                TableName: WATER_DEMAND_TABLE,
                KeyConditionExpression: 'parcelId = :parcelId',
                ExpressionAttributeValues: {
                    ':parcelId': parcel.id,
                },
                ScanIndexForward: false,
                Limit: 1,
            }).promise());
            const waterDemandResults = await Promise.all(waterDemandPromises);
            const summary = {
                zone,
                parcelCount: parcelsResult.Items.length,
                totalArea: parcelsResult.Items.reduce((sum, p) => sum + (p.area || 0), 0),
                waterDemandByMethod: {
                    'RID-MS': { count: 0, dailyDemand: 0, area: 0 },
                    'ROS': { count: 0, dailyDemand: 0, area: 0 },
                    'AWD': { count: 0, dailyDemand: 0, area: 0 },
                },
                totalDailyDemand: 0,
                totalWeeklyDemand: 0,
                totalMonthlyDemand: 0,
            };
            waterDemandResults.forEach((result, index) => {
                if (result.Items && result.Items.length > 0) {
                    const demand = result.Items[0];
                    const parcel = parcelsResult.Items[index];
                    const method = demand.method;
                    summary.waterDemandByMethod[method].count++;
                    summary.waterDemandByMethod[method].dailyDemand += demand.dailyDemand;
                    summary.waterDemandByMethod[method].area += parcel.area;
                    summary.totalDailyDemand += demand.dailyDemand;
                    summary.totalWeeklyDemand += demand.weeklyDemand;
                    summary.totalMonthlyDemand += demand.monthlyDemand;
                }
            });
            res.json(summary);
        }
        catch (error) {
            logger_1.logger.error('Error calculating water demand summary:', error);
            res.status(500).json({ error: 'Failed to calculate water demand summary' });
        }
    }
    async getGeoJSON(req, res) {
        try {
            const { shapeFileId } = req.params;
            const key = `processed/${shapeFileId}/parcels.geojson`;
            const s3Object = await s3.getObject({
                Bucket: PROCESSED_BUCKET,
                Key: key,
            }).promise();
            const geoJson = JSON.parse(s3Object.Body.toString());
            if (req.query.includeWaterDemand === 'true') {
                const enhancedFeatures = await Promise.all(geoJson.features.map(async (feature) => {
                    const waterDemandResult = await dynamodb.query({
                        TableName: WATER_DEMAND_TABLE,
                        KeyConditionExpression: 'parcelId = :parcelId',
                        ExpressionAttributeValues: {
                            ':parcelId': feature.properties.id,
                        },
                        ScanIndexForward: false,
                        Limit: 1,
                    }).promise();
                    if (waterDemandResult.Items && waterDemandResult.Items.length > 0) {
                        feature.properties.waterDemand = waterDemandResult.Items[0];
                    }
                    return feature;
                }));
                geoJson.features = enhancedFeatures;
            }
            res.json(geoJson);
        }
        catch (error) {
            logger_1.logger.error('Error fetching GeoJSON:', error);
            res.status(500).json({ error: 'Failed to fetch GeoJSON' });
        }
    }
    async getUploadUrl(req, res) {
        try {
            const { fileName, waterDemandMethod = 'RID-MS', processingInterval = 'weekly' } = req.body;
            if (!fileName) {
                return res.status(400).json({ error: 'fileName is required' });
            }
            const date = new Date().toISOString().split('T')[0];
            const key = `rid-ms/uploads/${date}/method-${waterDemandMethod}/interval-${processingInterval}/${fileName}`;
            const uploadUrl = await s3.getSignedUrlPromise('putObject', {
                Bucket: process.env.UPLOAD_BUCKET || 'rid-ms-uploads-dev',
                Key: key,
                Expires: 3600,
                ContentType: 'application/zip',
            });
            res.json({
                uploadUrl,
                key,
                expiresIn: 3600,
            });
        }
        catch (error) {
            logger_1.logger.error('Error generating upload URL:', error);
            res.status(500).json({ error: 'Failed to generate upload URL' });
        }
    }
    async updateWaterDemandMethod(req, res) {
        try {
            const { parcelIds, method } = req.body;
            if (!parcelIds || !Array.isArray(parcelIds) || parcelIds.length === 0) {
                return res.status(400).json({ error: 'parcelIds array is required' });
            }
            if (!['RID-MS', 'ROS', 'AWD'].includes(method)) {
                return res.status(400).json({ error: 'Invalid water demand method' });
            }
            const updatePromises = parcelIds.map(parcelId => dynamodb.update({
                TableName: PARCEL_TABLE,
                Key: { id: parcelId },
                UpdateExpression: 'SET waterDemandMethod = :method',
                ExpressionAttributeValues: {
                    ':method': method,
                },
            }).promise());
            await Promise.all(updatePromises);
            res.json({
                success: true,
                updatedCount: parcelIds.length,
                method,
            });
        }
        catch (error) {
            logger_1.logger.error('Error updating water demand method:', error);
            res.status(500).json({ error: 'Failed to update water demand method' });
        }
    }
}
exports.RidMsController = RidMsController;
//# sourceMappingURL=rid-ms.controller.js.map