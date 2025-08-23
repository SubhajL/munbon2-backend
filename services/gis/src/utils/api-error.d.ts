export declare class ApiError extends Error {
    statusCode: number;
    code?: string;
    details?: any;
    constructor(statusCode: number, message: string, details?: any, code?: string);
}
//# sourceMappingURL=api-error.d.ts.map