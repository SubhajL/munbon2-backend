import { Router } from 'express';
import { dataUploadController } from '@controllers/data-upload.controller';
import { etoDataController } from '@controllers/eto-data.controller';
import { uploadExcel } from '@middleware/file-upload';

const router = Router();

// Get monthly ETo data
router.get('/monthly', etoDataController.getMonthlyETo);

// Get all monthly ETo data for a station
router.get('/monthly/all', etoDataController.getAllMonthlyETo);

// Upload ETo data from Excel
router.post(
  '/upload',
  uploadExcel.single('file'),
  dataUploadController.uploadEToData
);

// Download ETo template
router.get('/template', dataUploadController.downloadEToTemplate);

export default router;