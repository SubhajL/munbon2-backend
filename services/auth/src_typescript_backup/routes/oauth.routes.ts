import { Router } from 'express';
import passport from 'passport';

const router = Router();

// Thai Digital ID OAuth
router.get('/thai-digital-id', passport.authenticate('thai-digital-id'));
router.get('/thai-digital-id/callback', 
  passport.authenticate('thai-digital-id', { 
    failureRedirect: '/login?error=oauth_failed' 
  }),
  (req, res) => {
    // Successful authentication
    res.redirect('/dashboard');
  }
);

export { router as oauthRoutes };