import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
export declare function validateRequest(schema: {
    body?: Joi.Schema;
    query?: Joi.Schema;
    params?: Joi.Schema;
}): (req: Request, res: Response, next: NextFunction) => void;
//# sourceMappingURL=validate-request.d.ts.map