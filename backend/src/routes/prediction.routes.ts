import { Router } from 'express';
import { predictCallback } from '../controllers/prediction.controller';
import { authenticate } from '../middleware/auth';

const router = Router();

router.use(authenticate);

router.post('/callback', predictCallback);

export default router;
