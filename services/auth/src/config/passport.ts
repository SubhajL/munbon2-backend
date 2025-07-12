import passport from 'passport';
import { Strategy as LocalStrategy } from 'passport-local';
import { Strategy as JwtStrategy, ExtractJwt } from 'passport-jwt';
import { Strategy as OAuth2Strategy } from 'passport-oauth2';
import { config } from './index';
import { userService } from '../services/user.service';
import { authService } from '../services/auth.service';
import { logger } from '../utils/logger';

export function setupPassport() {
  // Local Strategy
  passport.use(
    new LocalStrategy(
      {
        usernameField: 'email',
        passwordField: 'password',
      },
      async (email, password, done) => {
        try {
          const user = await authService.validateUser(email, password);
          if (!user) {
            return done(null, false, { message: 'Invalid credentials' });
          }
          return done(null, user);
        } catch (error) {
          logger.error('Local strategy error:', error);
          return done(error);
        }
      }
    )
  );

  // JWT Strategy
  passport.use(
    new JwtStrategy(
      {
        jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
        secretOrKey: config.jwt.secret,
        issuer: config.jwt.issuer,
        audience: config.jwt.audience,
      },
      async (payload, done) => {
        try {
          const user = await userService.findById(payload.sub);
          if (!user || !user.isActive) {
            return done(null, false);
          }
          return done(null, user);
        } catch (error) {
          logger.error('JWT strategy error:', error);
          return done(error, false);
        }
      }
    )
  );

  // Thai Digital ID OAuth2 Strategy
  passport.use(
    'thai-digital-id',
    new OAuth2Strategy(
      {
        authorizationURL: config.thaiDigitalId.authUrl,
        tokenURL: config.thaiDigitalId.tokenUrl,
        clientID: config.thaiDigitalId.clientId,
        clientSecret: config.thaiDigitalId.clientSecret,
        callbackURL: `${config.oauth.callbackUrl}/thai-digital-id`,
        scope: ['openid', 'profile', 'email', 'citizen_id'],
      },
      async (accessToken, refreshToken, profile, done) => {
        try {
          // Get user info from Thai Digital ID
          const userInfo = await authService.getThaiDigitalIdUserInfo(accessToken);
          
          // Find or create user
          const user = await authService.findOrCreateFromThaiDigitalId(userInfo);
          
          return done(null, user);
        } catch (error) {
          logger.error('Thai Digital ID strategy error:', error);
          return done(error);
        }
      }
    )
  );

  // Serialize user for session
  passport.serializeUser((user: any, done) => {
    done(null, user.id);
  });

  // Deserialize user from session
  passport.deserializeUser(async (id: string, done) => {
    try {
      const user = await userService.findById(id);
      done(null, user);
    } catch (error) {
      done(error);
    }
  });
}