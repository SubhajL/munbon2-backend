"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.handleMulterError = exports.uploadMiddleware = void 0;
const multer_1 = __importDefault(require("multer"));
const errorHandler_1 = require("./errorHandler");
// Configure multer for memory storage
const storage = multer_1.default.memoryStorage();
// File filter function
const fileFilter = (req, file, cb) => {
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
    }
    else {
        cb(new errorHandler_1.AppError(`Invalid file type. Allowed types: ${allowedTypes.join(', ')}`, 400));
    }
};
// Create multer instance
exports.uploadMiddleware = (0, multer_1.default)({
    storage: storage,
    fileFilter: fileFilter,
    limits: {
        fileSize: parseInt(process.env.MAX_FILE_SIZE || '52428800'), // 50MB default
        files: 1
    }
});
// Error handler for multer
const handleMulterError = (error, req, res, next) => {
    if (error instanceof multer_1.default.MulterError) {
        if (error.code === 'LIMIT_FILE_SIZE') {
            return next(new errorHandler_1.AppError('File size too large', 400));
        }
        if (error.code === 'LIMIT_FILE_COUNT') {
            return next(new errorHandler_1.AppError('Too many files', 400));
        }
        if (error.code === 'LIMIT_UNEXPECTED_FILE') {
            return next(new errorHandler_1.AppError('Unexpected field name', 400));
        }
    }
    next(error);
};
exports.handleMulterError = handleMulterError;
//# sourceMappingURL=uploadMiddleware.js.map