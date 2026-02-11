import { Router } from 'express';
import {
  createResume,
  getResumes,
  getResume,
  updateResume,
  deleteResume,
} from '../controllers/resume.controller';
import { authenticate } from '../middleware/auth';

const router = Router();

router.use(authenticate);

router.post('/', createResume);
router.get('/', getResumes);
router.get('/:id', getResume);
router.put('/:id', updateResume);
router.delete('/:id', deleteResume);

export default router;
