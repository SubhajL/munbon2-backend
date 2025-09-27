"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.adminRoutes = void 0;
const express_1 = require("express");
const authenticate_1 = require("../middleware/authenticate");
const authorize_1 = require("../middleware/authorize");
const permission_entity_1 = require("../models/permission.entity");
const router = (0, express_1.Router)();
exports.adminRoutes = router;
router.use(authenticate_1.authenticate);
router.use((0, authorize_1.authorize)(permission_entity_1.PERMISSIONS.SYSTEM_ADMIN));
router.get('/roles', (req, res) => {
    res.json({ message: 'List roles' });
});
router.get('/permissions', (req, res) => {
    res.json({ message: 'List permissions' });
});
router.get('/config', (req, res) => {
    res.json({ message: 'Get system config' });
});
router.get('/audit-logs', (req, res) => {
    res.json({ message: 'Get audit logs' });
});
//# sourceMappingURL=admin.routes.js.map