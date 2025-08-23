import { APIGatewayProxyHandler } from 'aws-lambda';
export declare const shapeFileUpload: APIGatewayProxyHandler;
export declare const shapeFileMetadata: APIGatewayProxyHandler;
export declare const shapeFileList: APIGatewayProxyHandler;
export declare const shapeFileParcels: APIGatewayProxyHandler;
export declare const shapeFileExport: APIGatewayProxyHandler;
export declare const processShapeFile: (event: any) => Promise<{
    statusCode: number;
    body: string;
}>;
//# sourceMappingURL=simple-handler.d.ts.map