"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.handler = void 0;
const aws_sdk_1 = __importDefault(require("aws-sdk"));
const dynamodb = new aws_sdk_1.default.DynamoDB.DocumentClient();
const sqs = new aws_sdk_1.default.SQS();
const PARCEL_TABLE = process.env.PARCEL_TABLE || 'rid-ms-parcels';
const WATER_DEMAND_TABLE = process.env.WATER_DEMAND_TABLE || 'rid-ms-water-demand';
const NOTIFICATION_QUEUE_URL = process.env.NOTIFICATION_QUEUE_URL || '';
const CROP_COEFFICIENTS = {
    'RICE': { initial: 1.05, mid: 1.20, late: 0.90 },
    'CORN': { initial: 0.30, mid: 1.20, late: 0.60 },
    'SUGARCANE': { initial: 0.40, mid: 1.25, late: 0.75 },
    'CASSAVA': { initial: 0.30, mid: 1.10, late: 0.50 },
    'VEGETABLES': { initial: 0.70, mid: 1.05, late: 0.95 },
    'DEFAULT': { initial: 0.50, mid: 1.00, late: 0.75 },
};
const IRRIGATION_EFFICIENCIES = {
    'RID-MS': 0.65,
    'ROS': 0.75,
    'AWD': 0.85,
};
const MONTHLY_ET0 = [4.0, 4.5, 5.0, 5.5, 5.0, 4.5, 4.0, 4.0, 4.0, 4.0, 3.5, 3.5];
const handler = async (event, context, callback) => {
    console.log('Water demand processor triggered:', JSON.stringify(event, null, 2));
    for (const record of event.Records) {
        try {
            const message = JSON.parse(record.body);
            if (message.type !== 'CALCULATE_WATER_DEMAND') {
                console.log(`Skipping message type: ${message.type}`);
                continue;
            }
            const parcels = await fetchParcels(message.shapeFileId);
            console.log(`Processing ${parcels.length} parcels for shape file ${message.shapeFileId}`);
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
        }
        catch (error) {
            console.error('Error processing water demand:', error);
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
exports.handler = handler;
async function fetchParcels(shapeFileId) {
    const parcels = [];
    let lastEvaluatedKey = undefined;
    do {
        const params = {
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
function calculateWaterDemand(parcel, method) {
    const cropType = parcel.cropType || 'DEFAULT';
    const cropCoeff = getCropCoefficient(cropType, parcel.plantingDate);
    const currentMonth = new Date().getMonth();
    const et0 = MONTHLY_ET0[currentMonth];
    const efficiency = IRRIGATION_EFFICIENCIES[method];
    const cropET = et0 * cropCoeff;
    let dailyDemand = (cropET * parcel.area) / (efficiency * 1000);
    if (method === 'AWD') {
        dailyDemand = dailyDemand * 0.7;
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
function getCropCoefficient(cropType, plantingDate) {
    const coefficients = CROP_COEFFICIENTS[cropType.toUpperCase()] || CROP_COEFFICIENTS['DEFAULT'];
    if (!plantingDate) {
        return coefficients.mid;
    }
    const daysSincePlanting = Math.floor((new Date().getTime() - new Date(plantingDate).getTime()) / (1000 * 60 * 60 * 24));
    if (daysSincePlanting < 30) {
        return coefficients.initial;
    }
    else if (daysSincePlanting < 90) {
        return coefficients.mid;
    }
    else {
        return coefficients.late;
    }
}
//# sourceMappingURL=water-demand-processor.js.map