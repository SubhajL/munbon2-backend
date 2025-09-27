"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.oauthRoutes = void 0;
const express_1 = require("express");
const passport_1 = __importDefault(require("passport"));
const router = (0, express_1.Router)();
exports.oauthRoutes = router;
router.get('/thai-digital-id', passport_1.default.authenticate('thai-digital-id'));
router.get('/thai-digital-id/callback', passport_1.default.authenticate('thai-digital-id', {
    failureRedirect: '/login?error=oauth_failed'
}), (req, res) => {
    res.redirect('/dashboard');
});
//# sourceMappingURL=oauth.routes.js.map