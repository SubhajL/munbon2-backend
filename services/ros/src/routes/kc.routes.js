"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const kc_data_controller_1 = require("@controllers/kc-data.controller");
const data_upload_controller_1 = require("@controllers/data-upload.controller");
const file_upload_1 = require("@middleware/file-upload");
const router = (0, express_1.Router)();
// Get Kc value for specific crop and week
router.get('/:cropType/week/:week', kc_data_controller_1.kcDataController.getKcValue);
// Get all Kc values for a crop type
router.get('/:cropType', kc_data_controller_1.kcDataController.getAllKcValues);
// Get crop summary
router.get('/summary/all', kc_data_controller_1.kcDataController.getCropSummary);
// Upload Kc data from Excel
router.post('/upload', file_upload_1.uploadExcel.single('file'), data_upload_controller_1.dataUploadController.uploadKcData);
// Download Kc template
router.get('/template/download', data_upload_controller_1.dataUploadController.downloadKcTemplate);
exports.default = router;
//# sourceMappingURL=kc.routes.js.map