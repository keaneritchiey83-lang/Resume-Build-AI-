import { Router } from 'express';
import { analyzeResume, getATSScore } from '../controllers/ats.controller';
import { authenticate } from '../middleware/auth';

const router = Router();

router.use(authenticate);

router.post('/analyze', analyzeResume);
router.get('/score/:resumeId', getATSScore);

export default router;
