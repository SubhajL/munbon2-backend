import multer from 'multer';
import { Request, Response, NextFunction } from 'express';
import { AppError } from './errorHandler';

// Configure multer for memory storage
const storage = multer.memoryStorage();

// File filter function
const fileFilter = (req: Request, file: Express.Multer.File, cb: multer.FileFilterCallback) => {
  // Allowed file types
  const allowedTypes = process.env.ALLOWED_FILE_TYPES?.split(',') || [
    '.xlsx',
    '.xls',
    '.csv',
    '.xlsm'
  ];

  const allowedMimeTypes = [
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel.sheet.macroEnabled.12',
    'text/csv'
  ];

  // Check file extension
  const fileExtension = '.' + file.originalname.split('.').pop()?.toLowerCase();
  const isAllowedExtension = allowedTypes.includes(fileExtension);

  // Check MIME type
  const isAllowedMimeType = allowedMimeTypes.includes(file.mimetype);

  if (isAllowedExtension && isAllowedMimeType) {
    cb(null, true);
  } else {
    cb(new AppError(`Invalid file type. Allowed types: ${allowedTypes.join(', ')}`, 400));
  }
};

// Create multer instance
export const uploadMiddleware = multer({
  storage: storage,
  fileFilter: fileFilter,
  limits: {
    fileSize: parseInt(process.env.MAX_FILE_SIZE || '52428800'), // 50MB default
    files: 1
  }
});

// Error handler for multer
export const handleMulterError = (error: any, req: Request, res: Response, next: NextFunction) => {
  if (error instanceof multer.MulterError) {
    if (error.code === 'LIMIT_FILE_SIZE') {
      return next(new AppError('File size too large', 400));
    }
    if (error.code === 'LIMIT_FILE_COUNT') {
      return next(new AppError('Too many files', 400));
    }
    if (error.code === 'LIMIT_UNEXPECTED_FILE') {
      return next(new AppError('Unexpected field name', 400));
    }
  }
  
  next(error);
};