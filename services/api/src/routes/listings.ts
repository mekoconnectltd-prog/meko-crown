import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { prisma } from '../lib/prisma';
import { requireAuth, requireRole } from '../middleware/auth';

const createSchema = z.object({
  title: z.string().min(5),
  description: z.string().min(20),
  assetType: z.enum(['EV_FLEET', 'COMMERCIAL_PROPERTY', 'EQUIPMENT']),
  value: z.number().positive(),
  location: z.string().min(1),
  noi: z.number().positive().optional(),
  tenant: z.string().optional(),
  leaseEnd: z.string().datetime().optional(),
});

export async function listingRoutes(app: FastifyInstance) {
  app.get('/', async (req) => {
    const query = req.query as { assetType?: string };
    const assetType = query.assetType && createSchema.shape.assetType.safeParse(query.assetType);

    return prisma.listing.findMany({
      where: assetType?.success ? { assetType: assetType.data } : {},
      orderBy: { createdAt: 'desc' },
      include: { seller: { select: { company: true, firstName: true } } },
    });
  });

  app.get('/:id', async (req, reply) => {
    const { id } = req.params as { id: string };
    const listing = await prisma.listing.findUnique({
      where: { id },
      include: { seller: { select: { company: true, email: true } } },
    });

    if (!listing) return reply.code(404).send({ error: 'Not found' });
    return listing;
  });

  app.post('/', { preHandler: [requireAuth, requireRole('SELLER')] }, async (req, reply) => {
    const body = createSchema.parse(req.body);
    const { userId } = req.user as { userId: string };

    return reply.code(201).send(await prisma.listing.create({
      data: {
        sellerId: userId,
        title: body.title,
        description: body.description,
        assetType: body.assetType,
        value: body.value,
        location: body.location,
        noi: body.noi,
        tenant: body.tenant,
        leaseEnd: body.leaseEnd ? new Date(body.leaseEnd) : null,
      },
    }));
  });
}
