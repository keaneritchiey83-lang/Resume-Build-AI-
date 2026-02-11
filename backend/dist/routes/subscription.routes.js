"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const subscription_controller_1 = require("../controllers/subscription.controller");
const auth_1 = require("../middleware/auth");
const express_2 = __importDefault(require("express"));
const router = (0, express_1.Router)();
// Webhook must come before express.json() middleware
router.post('/webhook', express_2.default.raw({ type: 'application/json' }), subscription_controller_1.handleWebhook);
router.use(auth_1.authenticate);
router.post('/checkout', subscription_controller_1.createCheckoutSession);
router.get('/', subscription_controller_1.getSubscription);
router.post('/cancel', subscription_controller_1.cancelSubscription);
exports.default = router;
//# sourceMappingURL=subscription.routes.js.map