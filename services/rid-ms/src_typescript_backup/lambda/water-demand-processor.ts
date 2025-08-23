import { SQSEvent, Context, Callback } from 'aws-lambda';
import AWS from 'aws-sdk';

const dynamodb = new AWS.DynamoDB.DocumentClient();
const sqs = new AWS.SQS();

const PARCEL_TABLE = process.env.PARCEL_TABLE || 'rid-ms-parcels';
const WATER_DEMAND_TABLE = process.env.WATER_DEMAND_TABLE || 'rid-ms-water-demand';
const NOTIFICATION_QUEUE_URL = process.env.NOTIFICATION_QUEUE_URL || '';

interface WaterDemandMessage {
  type: string;
  shapeFileId: string;
  parcelCount: number;
  waterDemandMethod: 'RID-MS' | 'ROS' | 'AWD';
  timestamp: string;
}

interface CropCoefficients {
  initial: number;
  mid: number;
  late: number;
}

// Crop coefficients for different crops
const CROP_COEFFICIENTS: Record<string, CropCoefficients> = {
  'RICE': { initial: 1.05, mid: 1.20, late: 0.90 },
  'CORN': { initial: 0.30, mid: 1.20, late: 0.60 },
  'SUGARCANE': { initial: 0.40, mid: 1.25, late: 0.75 },
  'CASSAVA': { initial: 0.30, mid: 1.10, late: 0.50 },
  'VEGETABLES': { initial: 0.70, mid: 1.05, late: 0.95 },
  'DEFAULT': { initial: 0.50, mid: 1.00, late: 0.75 },
};

// Irrigation efficiency by method
const IRRIGATION_EFFICIENCIES = {
  'RID-MS': 0.65,
  'ROS': 0.75,
  'AWD': 0.85,
};

// Monthly ET0 for Thailand (mm/day)
const MONTHLY_ET0 = [4.0, 4.5, 5.0, 5.5, 5.0, 4.5, 4.0, 4.0, 4.0, 4.0, 3.5, 3.5];

/**
 * Lambda handler for processing water demand calculations
 */
export const handler = async (event: SQSEvent, context: Context, callback: Callback) => {
  console.log('Water demand processor triggered:', JSON.stringify(event, null, 2));

  for (const record of event.Records) {
    try {
      const message: WaterDemandMessage = JSON.parse(record.body);

      if (message.type !== 'CALCULATE_WATER_DEMAND') {
        console.log(`Skipping message type: ${message.type}`);
        continue;
      }

      // Fetch parcels for the shape file
      const parcels = await fetchParcels(message.shapeFileId);
      console.log(`Processing ${parcels.length} parcels for shape file ${message.shapeFileId}`);

      // Calculate water demand for each parcel
      const waterDemandRecords = [];
      let totalDailyDemand = 0;
      let totalArea = 0;

      for (const parcel of parcels) {
        const waterDemand = calculateWaterDemand(parcel, message.waterDemandMethod);
        
        waterDemandRecords.push({
          parcelId: parcel.id,
          shapeFileId: message.shapeFileId,
          ...waterDemand,
          calculatedAt: new Date().toISOString(),
        });

        totalDailyDemand += waterDemand.dailyDemand;
        totalArea += parcel.area;
      }

      // Save water demand calculations in batches
      const BATCH_SIZE = 25;
      for (let i = 0; i < waterDemandRecords.length; i += BATCH_SIZE) {
        const batch = waterDemandRecords.slice(i, i + BATCH_SIZE);
        const putRequests = batch.map(record => ({
          PutRequest: { Item: record }
        }));

        await dynamodb.batchWrite({
          RequestItems: {
            [WATER_DEMAND_TABLE]: putRequests
          }
        }).promise();
      }

      // Send notification
      await sqs.sendMessage({
        QueueUrl: NOTIFICATION_QUEUE_URL,
        MessageBody: JSON.stringify({
          type: 'WATER_DEMAND_CALCULATED',
          shapeFileId: message.shapeFileId,
          parcelCount: parcels.length,
          totalArea,
          totalDailyDemand,
          averageDailyDemand: totalDailyDemand / parcels.length,
          method: message.waterDemandMethod,
          timestamp: new Date().toISOString(),
        }),
      }).promise();

      console.log(`Water demand calculation completed for shape file ${message.shapeFileId}`);

    } catch (error) {
      console.error('Error processing water demand:', error);
      
      // Send to DLQ
      await sqs.sendMessage({
        QueueUrl: process.env.DLQ_URL || '',
        MessageBody: JSON.stringify({
          type: 'WATER_DEMAND_PROCESSING_ERROR',
          originalMessage: record.body,
          error: error.message,
          timestamp: new Date().toISOString(),
        }),
      }).promise();
    }
  }
};

/**
 * Fetch parcels from DynamoDB
 */
async function fetchParcels(shapeFileId: string): Promise<any[]> {
  const parcels = [];
  let lastEvaluatedKey = undefined;

  do {
    const params: any = {
      TableName: PARCEL_TABLE,
      IndexName: 'shapeFileId-index',
      KeyConditionExpression: 'shapeFileId = :shapeFileId',
      ExpressionAttributeValues: {
        ':shapeFileId': shapeFileId,
      },
      ExclusiveStartKey: lastEvaluatedKey,
    };

    const result = await dynamodb.query(params).promise();
    parcels.push(...(result.Items || []));
    lastEvaluatedKey = result.LastEvaluatedKey;
  } while (lastEvaluatedKey);

  return parcels;
}

/**
 * Calculate water demand for a parcel
 */
function calculateWaterDemand(parcel: any, method: 'RID-MS' | 'ROS' | 'AWD') {
  // Get crop coefficient
  const cropType = parcel.cropType || 'DEFAULT';
  const cropCoeff = getCropCoefficient(cropType, parcel.plantingDate);

  // Get reference ET for current month
  const currentMonth = new Date().getMonth();
  const et0 = MONTHLY_ET0[currentMonth];

  // Get irrigation efficiency
  const efficiency = IRRIGATION_EFFICIENCIES[method];

  // Calculate crop water requirement (mm/day)
  const cropET = et0 * cropCoeff;

  // Convert to volume (m³/day)
  let dailyDemand = (cropET * parcel.area) / (efficiency * 1000);

  // Special adjustments for AWD method
  if (method === 'AWD') {
    dailyDemand = dailyDemand * 0.7; // 30% reduction
  }

  return {
    method,
    cropType,
    area: parcel.area,
    dailyDemand,
    weeklyDemand: dailyDemand * 7,
    monthlyDemand: dailyDemand * 30,
    seasonalDemand: dailyDemand * 120,
    cropCoefficient: cropCoeff,
    referenceET: et0,
    irrigationEfficiency: efficiency,
  };
}

/**
 * Get crop coefficient based on growth stage
 */
function getCropCoefficient(cropType: string, plantingDate?: string): number {
  const coefficients = CROP_COEFFICIENTS[cropType.toUpperCase()] || CROP_COEFFICIENTS['DEFAULT'];

  if (!plantingDate) {
    return coefficients.mid;
  }

  // Calculate days since planting
  const daysSincePlanting = Math.floor(
    (new Date().getTime() - new Date(plantingDate).getTime()) / (1000 * 60 * 60 * 24)
  );

  if (daysSincePlanting < 30) {
    return coefficients.initial;
  } else if (daysSincePlanting < 90) {
    return coefficients.mid;
  } else {
    return coefficients.late;
  }
}