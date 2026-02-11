"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const prediction_controller_1 = require("../controllers/prediction.controller");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
router.use(auth_1.authenticate);
router.post('/callback', prediction_controller_1.predictCallback);
exports.default = router;
//# sourceMappingURL=prediction.routes.js.map