const express = require('express');
const careerController = require('../controllers/careerController');
const { validateSkillGapAnalysis } = require('../middleware/validator');

const router = express.Router();

/**
 * POST /api/career/skills-gap
 * Analyze skill gap
 */
router.post('/skills-gap', validateSkillGapAnalysis, careerController.analyzeSkillGap);

module.exports = router;
