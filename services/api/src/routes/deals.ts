import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { prisma } from '../lib/prisma';
import { requireAuth } from '../middleware/auth';

const createDealSchema = z.object({
  listingId: z.string().min(1),
  deposit: z.number().nonnegative(),
  interestRate: z.number().nonnegative(),
  termMonths: z.number().int().positive(),
  monthlyPayment: z.number().positive(),
});

export async function dealRoutes(app: FastifyInstance) {
  app.get('/', { preHandler: [requireAuth] }, async (req) => {
    const { userId } = req.user as { userId: string };
    return prisma.deal.findMany({
      where: { buyerId: userId },
      include: { listing: true, payments: true, policy: true },
      orderBy: { createdAt: 'desc' },
    });
  });

  app.get('/:id', { preHandler: [requireAuth] }, async (req, reply) => {
    const { userId } = req.user as { userId: string };
    const { id } = req.params as { id: string };
    const deal = await prisma.deal.findFirst({
      where: { id, buyerId: userId },
      include: { listing: true, payments: true, policy: true },
    });

    if (!deal) return reply.code(404).send({ error: 'Deal not found' });
    return deal;
  });

  app.post('/', { preHandler: [requireAuth] }, async (req, reply) => {
    const body = createDealSchema.parse(req.body);
    const { userId } = req.user as { userId: string };
    const listing = await prisma.listing.findUnique({ where: { id: body.listingId } });

    if (!listing) return reply.code(404).send({ error: 'Listing not found' });
    if (listing.sellerId === userId) {
      return reply.code(400).send({ error: 'You cannot finance your own listing' });
    }

    const financeAmount = Number(listing.value) - body.deposit;
    if (financeAmount <= 0) {
      return reply.code(400).send({ error: 'Deposit must be less than the asset value' });
    }

    const deal = await prisma.deal.create({
      data: {
        buyerId: userId,
        listingId: listing.id,
        assetValue: listing.value,
        deposit: body.deposit,
        financeAmount,
        interestRate: body.interestRate,
        termMonths: body.termMonths,
        monthlyPayment: body.monthlyPayment,
        status: 'DRAFT',
      },
      include: { listing: true },
    });

    return reply.code(201).send(deal);
  });
}
