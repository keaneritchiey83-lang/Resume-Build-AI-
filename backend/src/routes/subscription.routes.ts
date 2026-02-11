import { Router } from 'express';
import {
  createCheckoutSession,
  handleWebhook,
  getSubscription,
  cancelSubscription,
} from '../controllers/subscription.controller';
import { authenticate } from '../middleware/auth';
import express from 'express';

const router = Router();

// Webhook must come before express.json() middleware
router.post(
  '/webhook',
  express.raw({ type: 'application/json' }),
  handleWebhook
);

router.use(authenticate);

router.post('/checkout', createCheckoutSession);
router.get('/', getSubscription);
router.post('/cancel', cancelSubscription);

export default router;
