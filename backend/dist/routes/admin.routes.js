"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const admin_controller_1 = require("../controllers/admin.controller");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
router.use(auth_1.authenticate);
router.use(auth_1.requireAdmin);
router.get('/stats', admin_controller_1.getDashboardStats);
router.get('/users', admin_controller_1.getAllUsers);
router.get('/users/:id', admin_controller_1.getUser);
router.put('/users/:id', admin_controller_1.updateUser);
router.delete('/users/:id', admin_controller_1.deleteUser);
router.get('/subscriptions', admin_controller_1.getAllSubscriptions);
exports.default = router;
//# sourceMappingURL=admin.routes.js.map