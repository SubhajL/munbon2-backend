"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.userController = void 0;
const user_service_1 = require("../services/user.service");
class UserController {
    async getProfile(req, res, next) {
        try {
            const user = await user_service_1.userService.findById(req.user.id);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async updateProfile(req, res, next) {
        try {
            const user = await user_service_1.userService.update(req.user.id, req.body, req.user.id);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async deleteAccount(req, res, next) {
        try {
            await user_service_1.userService.delete(req.user.id, req.user.id);
            res.json({ success: true, message: 'Account deleted successfully' });
        }
        catch (error) {
            next(error);
        }
    }
    async getUsers(req, res, next) {
        try {
            const { page = 1, limit = 20, ...filter } = req.query;
            const users = await user_service_1.userService.findAll(filter, {
                page: Number(page),
                limit: Number(limit)
            });
            res.json({ success: true, data: users });
        }
        catch (error) {
            next(error);
        }
    }
    async getUser(req, res, next) {
        try {
            const user = await user_service_1.userService.findById(req.params.id);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async updateUser(req, res, next) {
        try {
            const user = await user_service_1.userService.update(req.params.id, req.body, req.user.id);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async deleteUser(req, res, next) {
        try {
            await user_service_1.userService.delete(req.params.id, req.user.id);
            res.json({ success: true, message: 'User deleted successfully' });
        }
        catch (error) {
            next(error);
        }
    }
    async lockUser(req, res, next) {
        try {
            const user = await user_service_1.userService.updateStatus(req.params.id, 'locked', req.user.id, req.body.reason);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async unlockUser(req, res, next) {
        try {
            const user = await user_service_1.userService.updateStatus(req.params.id, 'active', req.user.id);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async assignRole(req, res, next) {
        try {
            const user = await user_service_1.userService.assignRole(req.params.id, req.body.roleId, req.user.id);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async revokeRole(req, res, next) {
        try {
            const user = await user_service_1.userService.revokeRole(req.params.id, req.params.roleId, req.user.id);
            res.json({ success: true, data: user });
        }
        catch (error) {
            next(error);
        }
    }
    async getUserAuditLogs(req, res, next) {
        try {
            res.json({ success: true, data: [] });
        }
        catch (error) {
            next(error);
        }
    }
}
exports.userController = new UserController();
//# sourceMappingURL=user.controller.js.map