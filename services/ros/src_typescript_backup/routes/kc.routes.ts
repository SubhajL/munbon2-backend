import { Router } from 'express';
import { kcDataController } from '@controllers/kc-data.controller';
import { dataUploadController } from '@controllers/data-upload.controller';
import { uploadExcel } from '@middleware/file-upload';

const router = Router();

// Get Kc value for specific crop and week
router.get('/:cropType/week/:week', kcDataController.getKcValue);

// Get all Kc values for a crop type
router.get('/:cropType', kcDataController.getAllKcValues);

// Get crop summary
router.get('/summary/all', kcDataController.getCropSummary);

// Upload Kc data from Excel
router.post(
  '/upload',
  uploadExcel.single('file'),
  dataUploadController.uploadKcData
);

// Download Kc template
router.get('/template/download', dataUploadController.downloadKcTemplate);

export default router;