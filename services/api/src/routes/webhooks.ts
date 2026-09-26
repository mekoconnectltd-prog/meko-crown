import { FastifyInstance } from 'fastify';
import Stripe from 'stripe';
import { prisma } from '../lib/prisma';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2024-06-20',
});

export async function webhookRoutes(app: FastifyInstance) {
  app.post('/', {
    config: {
      rawBody: true,
    },
  }, async (request, reply) => {
    const signature = request.headers['stripe-signature'];
    const secret = process.env.STRIPE_WEBHOOK_SECRET;

    if (!secret) {
      return reply.code(500).send({ error: 'Webhook secret not configured' });
    }

    if (!signature || Array.isArray(signature)) {
      return reply.code(400).send({ error: 'Missing Stripe signature' });
    }

    const rawBody = request.rawBody;
    if (!rawBody || !(rawBody instanceof Buffer)) {
      return reply.code(400).send({ error: 'Missing raw request body' });
    }

    let event;

    try {
      event = stripe.webhooks.constructEvent(rawBody, signature, secret);
    } catch (error) {
      return reply.code(400).send({ error: 'Invalid Stripe signature' });
    }

    const eventType = event.type;
    const data = event.data.object as any;

    try {
      if (eventType === 'charge.succeeded') {
        const paymentId = data.metadata?.paymentId;
        if (paymentId) {
          await prisma.payment.update({
            where: { id: paymentId },
            data: { status: 'PAID', paidDate: new Date() },
          });
        }
      }

      if (eventType === 'charge.failed') {
        const paymentId = data.metadata?.paymentId;
        if (paymentId) {
          await prisma.payment.update({
            where: { id: paymentId },
            data: { status: 'FAILED' },
          });
        }
      }

      if (eventType === 'invoice.payment_failed') {
        const paymentId = data.metadata?.paymentId;
        if (paymentId) {
          await prisma.payment.update({
            where: { id: paymentId },
            data: { status: 'OVERDUE' },
          });
        }
      }

      return reply.code(200).send({ received: true, type: eventType });
    } catch (error) {
      return reply.code(500).send({ error: 'Failed to process webhook' });
    }
  });
}
