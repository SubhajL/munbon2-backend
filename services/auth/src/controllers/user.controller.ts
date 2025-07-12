import { Request, Response, NextFunction } from 'express';
import { userService } from '../services/user.service';

class UserController {
  async getProfile(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.findById(req.user!.id);
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async updateProfile(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.update(req.user!.id, req.body, req.user!.id);
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async deleteAccount(req: Request, res: Response, next: NextFunction) {
    try {
      await userService.delete(req.user!.id, req.user!.id);
      res.json({ success: true, message: 'Account deleted successfully' });
    } catch (error) {
      next(error);
    }
  }

  async getUsers(req: Request, res: Response, next: NextFunction) {
    try {
      const { page = 1, limit = 20, ...filter } = req.query;
      const users = await userService.findAll(filter, { 
        page: Number(page), 
        limit: Number(limit) 
      });
      res.json({ success: true, data: users });
    } catch (error) {
      next(error);
    }
  }

  async getUser(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.findById(req.params.id);
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async updateUser(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.update(req.params.id, req.body, req.user!.id);
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async deleteUser(req: Request, res: Response, next: NextFunction) {
    try {
      await userService.delete(req.params.id, req.user!.id);
      res.json({ success: true, message: 'User deleted successfully' });
    } catch (error) {
      next(error);
    }
  }

  async lockUser(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.updateStatus(
        req.params.id, 
        'locked', 
        req.user!.id,
        req.body.reason
      );
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async unlockUser(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.updateStatus(
        req.params.id, 
        'active', 
        req.user!.id
      );
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async assignRole(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.assignRole(
        req.params.id,
        req.body.roleId,
        req.user!.id
      );
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async revokeRole(req: Request, res: Response, next: NextFunction) {
    try {
      const user = await userService.revokeRole(
        req.params.id,
        req.params.roleId,
        req.user!.id
      );
      res.json({ success: true, data: user });
    } catch (error) {
      next(error);
    }
  }

  async getUserAuditLogs(req: Request, res: Response, next: NextFunction) {
    try {
      // TODO: Implement audit log retrieval
      res.json({ success: true, data: [] });
    } catch (error) {
      next(error);
    }
  }
}

export const userController = new UserController();