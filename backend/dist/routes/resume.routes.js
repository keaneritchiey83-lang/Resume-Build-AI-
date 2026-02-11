"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const resume_controller_1 = require("../controllers/resume.controller");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
router.use(auth_1.authenticate);
router.post('/', resume_controller_1.createResume);
router.get('/', resume_controller_1.getResumes);
router.get('/:id', resume_controller_1.getResume);
router.put('/:id', resume_controller_1.updateResume);
router.delete('/:id', resume_controller_1.deleteResume);
exports.default = router;
//# sourceMappingURL=resume.routes.js.map