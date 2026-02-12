const { body, validationResult } = require('express-validator');

/**
 * Validation middleware to check for validation errors
 */
const validate = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({
      success: false,
      errors: errors.array(),
    });
  }
  next();
};

/**
 * Validation rules for resume generation
 */
const validateResumeGeneration = [
  body('jobDescription').notEmpty().trim().withMessage('Job description is required'),
  body('experience').isArray({ min: 1 }).withMessage('Experience must be a non-empty array'),
  body('resumeType').optional().isIn(['private', 'federal']).withMessage('Invalid resume type'),
  validate,
];

/**
 * Validation rules for resume optimization
 */
const validateResumeOptimization = [
  body('resumeContent').notEmpty().trim().withMessage('Resume content is required'),
  body('jobDescription').notEmpty().trim().withMessage('Job description is required'),
  validate,
];

/**
 * Validation rules for interview preparation
 */
const validateInterviewPreparation = [
  body('jobDescription').notEmpty().trim().withMessage('Job description is required'),
  body('interviewType').isIn(['behavioral', 'technical', 'federal']).withMessage('Invalid interview type'),
  validate,
];

/**
 * Validation rules for skill gap analysis
 */
const validateSkillGapAnalysis = [
  body('currentSkills').isArray({ min: 1 }).withMessage('Current skills must be a non-empty array'),
  body('jobDescription').notEmpty().trim().withMessage('Job description is required'),
  validate,
];

module.exports = {
  validate,
  validateResumeGeneration,
  validateResumeOptimization,
  validateInterviewPreparation,
  validateSkillGapAnalysis,
};
