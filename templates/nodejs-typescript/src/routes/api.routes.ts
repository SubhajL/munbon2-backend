import { Router } from 'express';
// Import your API route modules here

export const apiRouter = Router();

/**
 * @swagger
 * components:
 *   schemas:
 *     Error:
 *       type: object
 *       properties:
 *         error:
 *           type: object
 *           properties:
 *             message:
 *               type: string
 *             stack:
 *               type: string
 *               description: Only included in development mode
 */

// Add your API routes here
// apiRouter.use('/users', userRouter);
// apiRouter.use('/resources', resourceRouter);