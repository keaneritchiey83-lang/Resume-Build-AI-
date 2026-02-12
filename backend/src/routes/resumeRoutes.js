const express = require('express');
const resumeController = require('../controllers/resumeController');
const {
  validateResumeGeneration,
  validateResumeOptimization,
} = require('../middleware/validator');

const router = express.Router();

/**
 * POST /api/resume/generate
 * Generate a new resume
 */
router.post('/generate', validateResumeGeneration, resumeController.generateResume);

/**
 * POST /api/resume/optimize
 * Optimize resume for ATS
 */
router.post('/optimize', validateResumeOptimization, resumeController.optimizeResume);

module.exports = router;
