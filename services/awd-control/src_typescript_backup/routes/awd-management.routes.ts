import { Router } from 'express';
import { awdManagementController } from '../controllers/awd-management.controller';

export const awdManagementRouter = Router();

// Initialize AWD control for a field
awdManagementRouter.post('/initialize', awdManagementController.initializeField);

// Get control decision for a field
awdManagementRouter.get('/decision/:fieldId', awdManagementController.getControlDecision);

// Update section start dates
awdManagementRouter.post('/section/start-dates', awdManagementController.updateSectionStartDates);

// Get AWD schedule template
awdManagementRouter.get('/schedule/:plantingMethod', awdManagementController.getSchedule);