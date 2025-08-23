"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.shapeFileRoutes = void 0;
const express_1 = require("express");
const multer_1 = __importDefault(require("multer"));
const shapefile_controller_1 = require("../controllers/shapefile.controller");
const auth_1 = require("../middleware/auth");
const authorize_1 = require("../middleware/authorize");
const validate_request_1 = require("../middleware/validate-request");
const shapefile_zod_validator_1 = require("../validators/shapefile-zod.validator");
const router = (0, express_1.Router)();
exports.shapeFileRoutes = router;
const controller = new shapefile_controller_1.ShapeFileController();
const upload = (0, multer_1.default)({
    storage: multer_1.default.memoryStorage(),
    limits: {
        fileSize: 100 * 1024 * 1024,
    },
    fileFilter: (req, file, cb) => {
        const filename = file.originalname.toLowerCase();
        if (file.mimetype === 'application/zip' || filename.endsWith('.zip') ||
            file.mimetype === 'application/geopackage+sqlite3' || filename.endsWith('.gpkg')) {
            cb(null, true);
        }
        else {
            cb(new Error('Only .zip (shapefile) and .gpkg (GeoPackage) files are allowed'));
        }
    },
});
router.post('/upload', auth_1.authenticate, (0, authorize_1.authorize)(['admin', 'operator']), upload.single('file'), (0, validate_request_1.validateRequest)(shapefile_zod_validator_1.shapeFileUploadValidator), controller.uploadShapeFile);
router.get('/uploads', auth_1.authenticate, controller.listUploads);
router.get('/uploads/:uploadId', auth_1.authenticate, controller.getUploadStatus);
router.get('/uploads/:uploadId/parcels', auth_1.authenticate, controller.getUploadParcels);
router.delete('/uploads/:uploadId', auth_1.authenticate, (0, authorize_1.authorize)(['admin']), controller.deleteUpload);
router.post('/external/upload', upload.single('file'), controller.externalUpload);
//# sourceMappingURL=shapefile.routes.js.map