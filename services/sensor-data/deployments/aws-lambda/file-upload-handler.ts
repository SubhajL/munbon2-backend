// DEPRECATED: Shape file uploads have been moved to the GIS service
// This handler is kept for backward compatibility but should not be used
// New endpoint: POST /api/v1/gis/shapefile/upload
// GIS Lambda deployment: /services/gis/deployments/aws-lambda/

import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';

/**
 * @deprecated Shape file uploads have been moved to GIS service
 */
export const handler = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  return {
    statusCode: 410, // Gone
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      error: 'This endpoint has been deprecated',
      message: 'Shape file uploads have been moved to the GIS service',
      newEndpoint: '/api/v1/gis/shapefile/upload',
      documentation: 'Please update your integration to use the GIS service endpoints'
    })
  };
};