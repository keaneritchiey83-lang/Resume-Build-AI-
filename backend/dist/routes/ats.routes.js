"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const ats_controller_1 = require("../controllers/ats.controller");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
router.use(auth_1.authenticate);
router.post('/analyze', ats_controller_1.analyzeResume);
router.get('/score/:resumeId', ats_controller_1.getATSScore);
exports.default = router;
//# sourceMappingURL=ats.routes.js.map