import { Router } from 'express';
import { authController } from '../controllers/auth.controller';
import { validateRequest } from '../middleware/validate-request';
import { authenticate } from '../middleware/authenticate';
import { 
  loginSchema, 
  registerSchema, 
  refreshTokenSchema,
  forgotPasswordSchema,
  resetPasswordSchema,
  changePasswordSchema
} from '../validators/auth.validator';

const router = Router();

// Public routes
router.post('/register', validateRequest(registerSchema), authController.register);
router.post('/login', validateRequest(loginSchema), authController.login);
router.post('/refresh', validateRequest(refreshTokenSchema), authController.refreshToken);
router.post('/logout', authController.logout);
router.post('/forgot-password', validateRequest(forgotPasswordSchema), authController.forgotPassword);
router.post('/reset-password', validateRequest(resetPasswordSchema), authController.resetPassword);
router.get('/verify-email/:token', authController.verifyEmail);

// Protected routes
router.use(authenticate);
router.get('/me', authController.getCurrentUser);
router.post('/change-password', validateRequest(changePasswordSchema), authController.changePassword);
router.post('/enable-2fa', authController.enable2FA);
router.post('/disable-2fa', authController.disable2FA);
router.post('/verify-2fa', authController.verify2FA);
router.get('/sessions', authController.getSessions);
router.delete('/sessions/:sessionId', authController.revokeSession);

export { router as authRoutes };