const express = require('express');
const interviewController = require('../controllers/interviewController');
const { validateInterviewPreparation } = require('../middleware/validator');

const router = express.Router();

/**
 * POST /api/interview/prepare
 * Generate interview questions
 */
router.post('/prepare', validateInterviewPreparation, interviewController.prepareInterview);

module.exports = router;
