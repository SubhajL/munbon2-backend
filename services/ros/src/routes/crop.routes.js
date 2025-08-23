"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const router = (0, express_1.Router)();
// TODO: Implement crop routes
router.get('/', (req, res) => {
    res.status(501).json({ message: 'Crop management endpoints not yet implemented' });
});
exports.default = router;
//# sourceMappingURL=crop.routes.js.map