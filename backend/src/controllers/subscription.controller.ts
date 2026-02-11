import { Request, Response } from 'express';
import Stripe from 'stripe';
import { PrismaClient } from '@prisma/client';
import { AuthRequest } from '../middleware/auth';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2023-10-16',
});

const prisma = new PrismaClient();

export const createCheckoutSession = async (req: AuthRequest, res: Response) => {
  try {
    const { tier } = req.body; // 'PRO' or 'ENTERPRISE'

    if (!tier || !['PRO', 'ENTERPRISE'].includes(tier)) {
      return res.status(400).json({ message: 'Invalid subscription tier' });
    }

    const user = await prisma.user.findUnique({
      where: { id: req.userId! },
    });

    if (!user) {
      return res.status(404).json({ message: 'User not found' });
    }

    // Get or create Stripe customer
    let customerId = user.stripeCustomerId;
    if (!customerId) {
      const customer = await stripe.customers.create({
        email: user.email,
        metadata: {
          userId: user.id,
        },
      });
      customerId = customer.id;
      await prisma.user.update({
        where: { id: user.id },
        data: { stripeCustomerId: customerId },
      });
    }

    // Get price ID based on tier
    const priceId = tier === 'PRO'
      ? process.env.STRIPE_PRICE_ID_PRO
      : process.env.STRIPE_PRICE_ID_ENTERPRISE;

    if (!priceId) {
      return res.status(500).json({ message: 'Stripe price not configured' });
    }

    // Create checkout session
    const session = await stripe.checkout.sessions.create({
      customer: customerId,
      mode: 'subscription',
      payment_method_types: ['card'],
      line_items: [
        {
          price: priceId,
          quantity: 1,
        },
      ],
      success_url: `${process.env.CORS_ORIGIN}/dashboard?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${process.env.CORS_ORIGIN}/pricing`,
      metadata: {
        userId: user.id,
        tier,
      },
    });

    res.json({ success: true, data: { sessionUrl: session.url } });
  } catch (error) {
    console.error('Create checkout session error:', error);
    res.status(500).json({ message: 'Error creating checkout session' });
  }
};

export const handleWebhook = async (req: Request, res: Response) => {
  const sig = req.headers['stripe-signature'] as string;
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

  if (!webhookSecret) {
    return res.status(500).send('Webhook secret not configured');
  }

  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
  } catch (err: any) {
    console.error('Webhook signature verification failed:', err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed':
        await handleCheckoutComplete(event.data.object as Stripe.Checkout.Session);
        break;

      case 'customer.subscription.updated':
        await handleSubscriptionUpdate(event.data.object as Stripe.Subscription);
        break;

      case 'customer.subscription.deleted':
        await handleSubscriptionDelete(event.data.object as Stripe.Subscription);
        break;

      default:
        console.log(`Unhandled event type: ${event.type}`);
    }

    res.json({ received: true });
  } catch (error) {
    console.error('Webhook handler error:', error);
    res.status(500).json({ message: 'Webhook handler failed' });
  }
};

export const getSubscription = async (req: AuthRequest, res: Response) => {
  try {
    const subscription = await prisma.subscription.findUnique({
      where: { userId: req.userId! },
    });

    if (!subscription) {
      return res.status(404).json({ message: 'Subscription not found' });
    }

    res.json({ success: true, data: subscription });
  } catch (error) {
    console.error('Get subscription error:', error);
    res.status(500).json({ message: 'Error fetching subscription' });
  }
};

export const cancelSubscription = async (req: AuthRequest, res: Response) => {
  try {
    const subscription = await prisma.subscription.findUnique({
      where: { userId: req.userId! },
    });

    if (!subscription || !subscription.stripeSubscriptionId) {
      return res.status(404).json({ message: 'Active subscription not found' });
    }

    // Cancel at period end in Stripe
    await stripe.subscriptions.update(subscription.stripeSubscriptionId, {
      cancel_at_period_end: true,
    });

    // Update database
    const updated = await prisma.subscription.update({
      where: { userId: req.userId! },
      data: { cancelAtPeriodEnd: true },
    });

    res.json({ success: true, data: updated });
  } catch (error) {
    console.error('Cancel subscription error:', error);
    res.status(500).json({ message: 'Error canceling subscription' });
  }
};

// Helper functions for webhook handlers
async function handleCheckoutComplete(session: Stripe.Checkout.Session) {
  const userId = session.metadata?.userId;
  const tier = session.metadata?.tier;

  if (!userId || !tier) {
    console.error('Missing metadata in checkout session');
    return;
  }

  const stripeSubscription = await stripe.subscriptions.retrieve(
    session.subscription as string
  );

  await prisma.subscription.update({
    where: { userId },
    data: {
      tier: tier as any,
      status: 'ACTIVE',
      stripeSubscriptionId: stripeSubscription.id,
      currentPeriodEnd: new Date(stripeSubscription.current_period_end * 1000),
    },
  });
}

async function handleSubscriptionUpdate(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string;
  const user = await prisma.user.findFirst({
    where: { stripeCustomerId: customerId },
  });

  if (!user) {
    console.error('User not found for customer:', customerId);
    return;
  }

  await prisma.subscription.update({
    where: { userId: user.id },
    data: {
      status: subscription.status === 'active' ? 'ACTIVE' : 'INACTIVE',
      currentPeriodEnd: new Date(subscription.current_period_end * 1000),
    },
  });
}

async function handleSubscriptionDelete(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string;
  const user = await prisma.user.findFirst({
    where: { stripeCustomerId: customerId },
  });

  if (!user) {
    console.error('User not found for customer:', customerId);
    return;
  }

  await prisma.subscription.update({
    where: { userId: user.id },
    data: {
      tier: 'FREE',
      status: 'CANCELED',
      stripeSubscriptionId: null,
      currentPeriodEnd: null,
    },
  });
}
