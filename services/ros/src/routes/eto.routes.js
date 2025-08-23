"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const data_upload_controller_1 = require("@controllers/data-upload.controller");
const eto_data_controller_1 = require("@controllers/eto-data.controller");
const file_upload_1 = require("@middleware/file-upload");
const router = (0, express_1.Router)();
// Get monthly ETo data
router.get('/monthly', eto_data_controller_1.etoDataController.getMonthlyETo);
// Get all monthly ETo data for a station
router.get('/monthly/all', eto_data_controller_1.etoDataController.getAllMonthlyETo);
// Upload ETo data from Excel
router.post('/upload', file_upload_1.uploadExcel.single('file'), data_upload_controller_1.dataUploadController.uploadEToData);
// Download ETo template
router.get('/template', data_upload_controller_1.dataUploadController.downloadEToTemplate);
exports.default = router;
//# sourceMappingURL=eto.routes.js.map