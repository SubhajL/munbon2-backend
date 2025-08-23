import rateLimit from 'express-rate-limit';
import { Request, Response } from 'express';

export const rateLimiter = rateLimit({
  windowMs: parseInt(process.env.API_RATE_WINDOW || '15') * 60 * 1000, // minutes to milliseconds
  max: parseInt(process.env.API_RATE_LIMIT || '100'),
  message: 'Too many requests from this IP, please try again later.',
  standardHeaders: true,
  legacyHeaders: false,
  handler: (req: Request, res: Response) => {
    res.status(429).json({
      success: false,
      error: {
        message: 'Too many requests, please try again later.',
        retryAfter: req.rateLimit?.resetTime,
      },
    });
  },
});

// Create specific rate limiters for different endpoints
export const uploadRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 10, // limit each IP to 10 uploads per windowMs
  message: 'Too many file uploads, please try again later.',
});

export const calculationRateLimiter = rateLimit({
  windowMs: 5 * 60 * 1000, // 5 minutes
  max: 20, // limit each IP to 20 calculations per windowMs
  message: 'Too many calculation requests, please try again later.',
});