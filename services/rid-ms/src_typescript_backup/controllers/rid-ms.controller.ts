import { Request, Response } from 'express';
import AWS from 'aws-sdk';
import { logger } from '../utils/logger';

const dynamodb = new AWS.DynamoDB.DocumentClient({
  region: process.env.AWS_REGION || 'ap-southeast-1',
});

const s3 = new AWS.S3({
  region: process.env.AWS_REGION || 'ap-southeast-1',
});

const SHAPE_FILE_TABLE = process.env.SHAPE_FILE_TABLE || 'rid-ms-shapefiles-dev';
const PARCEL_TABLE = process.env.PARCEL_TABLE || 'rid-ms-parcels-dev';
const WATER_DEMAND_TABLE = process.env.WATER_DEMAND_TABLE || 'rid-ms-water-demand-dev';
const PROCESSED_BUCKET = process.env.PROCESSED_BUCKET || 'rid-ms-processed-dev';

export class RidMsController {
  /**
   * Get all shape files with pagination
   */
  async getShapeFiles(req: Request, res: Response) {
    try {
      const { status, limit = 20, lastKey } = req.query;

      const params: any = {
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
        params.ExclusiveStartKey = JSON.parse(lastKey as string);
      }

      const result = await dynamodb.query(params).promise();

      res.json({
        items: result.Items,
        lastKey: result.LastEvaluatedKey,
        count: result.Items?.length || 0,
      });
    } catch (error) {
      logger.error('Error fetching shape files:', error);
      res.status(500).json({ error: 'Failed to fetch shape files' });
    }
  }

  /**
   * Get shape file details by ID
   */
  async getShapeFileById(req: Request, res: Response) {
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
    } catch (error) {
      logger.error('Error fetching shape file:', error);
      res.status(500).json({ error: 'Failed to fetch shape file' });
    }
  }

  /**
   * Get parcels by shape file ID
   */
  async getParcelsByShapeFile(req: Request, res: Response) {
    try {
      const { shapeFileId } = req.params;
      const { limit = 100, lastKey } = req.query;

      const params: any = {
        TableName: PARCEL_TABLE,
        IndexName: 'shapeFileId-index',
        KeyConditionExpression: 'shapeFileId = :shapeFileId',
        ExpressionAttributeValues: {
          ':shapeFileId': shapeFileId,
        },
        Limit: Number(limit),
      };

      if (lastKey) {
        params.ExclusiveStartKey = JSON.parse(lastKey as string);
      }

      const result = await dynamodb.query(params).promise();

      res.json({
        items: result.Items,
        lastKey: result.LastEvaluatedKey,
        count: result.Items?.length || 0,
      });
    } catch (error) {
      logger.error('Error fetching parcels:', error);
      res.status(500).json({ error: 'Failed to fetch parcels' });
    }
  }

  /**
   * Get parcels by zone
   */
  async getParcelsByZone(req: Request, res: Response) {
    try {
      const { zone } = req.params;
      const { waterDemandMethod, limit = 100, lastKey } = req.query;

      const params: any = {
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
        params.ExclusiveStartKey = JSON.parse(lastKey as string);
      }

      const result = await dynamodb.query(params).promise();

      res.json({
        items: result.Items,
        lastKey: result.LastEvaluatedKey,
        count: result.Items?.length || 0,
      });
    } catch (error) {
      logger.error('Error fetching parcels by zone:', error);
      res.status(500).json({ error: 'Failed to fetch parcels' });
    }
  }

  /**
   * Get water demand for a parcel
   */
  async getParcelWaterDemand(req: Request, res: Response) {
    try {
      const { parcelId } = req.params;

      // Get latest water demand calculation
      const result = await dynamodb.query({
        TableName: WATER_DEMAND_TABLE,
        KeyConditionExpression: 'parcelId = :parcelId',
        ExpressionAttributeValues: {
          ':parcelId': parcelId,
        },
        ScanIndexForward: false, // Get latest first
        Limit: 1,
      }).promise();

      if (!result.Items || result.Items.length === 0) {
        return res.status(404).json({ error: 'Water demand not found' });
      }

      res.json(result.Items[0]);
    } catch (error) {
      logger.error('Error fetching water demand:', error);
      res.status(500).json({ error: 'Failed to fetch water demand' });
    }
  }

  /**
   * Get water demand summary by zone
   */
  async getWaterDemandSummaryByZone(req: Request, res: Response) {
    try {
      const { zone } = req.params;

      // First get all parcels in the zone
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

      // Get water demand for each parcel
      const waterDemandPromises = parcelsResult.Items.map(parcel =>
        dynamodb.query({
          TableName: WATER_DEMAND_TABLE,
          KeyConditionExpression: 'parcelId = :parcelId',
          ExpressionAttributeValues: {
            ':parcelId': parcel.id,
          },
          ScanIndexForward: false,
          Limit: 1,
        }).promise()
      );

      const waterDemandResults = await Promise.all(waterDemandPromises);

      // Calculate summary
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
          const parcel = parcelsResult.Items![index];
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
    } catch (error) {
      logger.error('Error calculating water demand summary:', error);
      res.status(500).json({ error: 'Failed to calculate water demand summary' });
    }
  }

  /**
   * Get GeoJSON for visualization
   */
  async getGeoJSON(req: Request, res: Response) {
    try {
      const { shapeFileId } = req.params;

      // Get processed GeoJSON from S3
      const key = `processed/${shapeFileId}/parcels.geojson`;
      
      const s3Object = await s3.getObject({
        Bucket: PROCESSED_BUCKET,
        Key: key,
      }).promise();

      const geoJson = JSON.parse(s3Object.Body!.toString());

      // Optionally enhance with water demand data
      if (req.query.includeWaterDemand === 'true') {
        // Fetch water demand for each feature
        const enhancedFeatures = await Promise.all(
          geoJson.features.map(async (feature: any) => {
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
          })
        );

        geoJson.features = enhancedFeatures;
      }

      res.json(geoJson);
    } catch (error) {
      logger.error('Error fetching GeoJSON:', error);
      res.status(500).json({ error: 'Failed to fetch GeoJSON' });
    }
  }

  /**
   * Get upload presigned URL
   */
  async getUploadUrl(req: Request, res: Response) {
    try {
      const { fileName, waterDemandMethod = 'RID-MS', processingInterval = 'weekly' } = req.body;

      if (!fileName) {
        return res.status(400).json({ error: 'fileName is required' });
      }

      // Generate S3 key with metadata in path
      const date = new Date().toISOString().split('T')[0];
      const key = `rid-ms/uploads/${date}/method-${waterDemandMethod}/interval-${processingInterval}/${fileName}`;

      const uploadUrl = await s3.getSignedUrlPromise('putObject', {
        Bucket: process.env.UPLOAD_BUCKET || 'rid-ms-uploads-dev',
        Key: key,
        Expires: 3600, // 1 hour
        ContentType: 'application/zip',
      });

      res.json({
        uploadUrl,
        key,
        expiresIn: 3600,
      });
    } catch (error) {
      logger.error('Error generating upload URL:', error);
      res.status(500).json({ error: 'Failed to generate upload URL' });
    }
  }

  /**
   * Update water demand method for parcels
   */
  async updateWaterDemandMethod(req: Request, res: Response) {
    try {
      const { parcelIds, method } = req.body;

      if (!parcelIds || !Array.isArray(parcelIds) || parcelIds.length === 0) {
        return res.status(400).json({ error: 'parcelIds array is required' });
      }

      if (!['RID-MS', 'ROS', 'AWD'].includes(method)) {
        return res.status(400).json({ error: 'Invalid water demand method' });
      }

      // Update each parcel
      const updatePromises = parcelIds.map(parcelId =>
        dynamodb.update({
          TableName: PARCEL_TABLE,
          Key: { id: parcelId },
          UpdateExpression: 'SET waterDemandMethod = :method',
          ExpressionAttributeValues: {
            ':method': method,
          },
        }).promise()
      );

      await Promise.all(updatePromises);

      // Trigger recalculation
      // In a real implementation, this would send a message to SQS
      // to trigger the water demand calculation Lambda

      res.json({
        success: true,
        updatedCount: parcelIds.length,
        method,
      });
    } catch (error) {
      logger.error('Error updating water demand method:', error);
      res.status(500).json({ error: 'Failed to update water demand method' });
    }
  }
}