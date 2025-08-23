import { Request, Response, NextFunction } from 'express';
export declare class AppError extends Error {
    statusCode: number;
    message: string;
    isOperational: boolean;
    details?: any | undefined;
    constructor(statusCode: number, message: string, isOperational?: boolean, details?: any | undefined);
}
export declare const errorHandler: (err: Error | AppError, req: Request, res: Response, _next: NextFunction) => void;
//# sourceMappingURL=errorHandler.d.ts.map