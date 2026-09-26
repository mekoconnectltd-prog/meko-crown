import Fastify from 'fastify';
import cors from '@fastify/cors';
import jwt from '@fastify/jwt';
import multipart from '@fastify/multipart';
import { authRoutes } from './routes/auth';
import { listingRoutes } from './routes/listings';
import { dealRoutes } from './routes/deals';
import { webhookRoutes } from './routes/webhooks';

const PORT = parseInt(process.env.PORT || '3001', 10);
const HOST = '0.0.0.0';
const JWT_SECRET = process.env.JWT_SECRET;

if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required');
}

async function start() {
  const app = Fastify({
    logger: true,
  });

  // Register plugins
  await app.register(cors, { origin: true });
  await app.register(jwt, { secret: JWT_SECRET });
  await app.register(multipart);

  // Health check
  app.get('/health', async (req, reply) => {
    return { ok: true };
  });

  // Register routes
  await app.register(authRoutes, { prefix: '/auth' });
  await app.register(listingRoutes, { prefix: '/listings' });
  await app.register(dealRoutes, { prefix: '/deals' });
  await app.register(webhookRoutes, { prefix: '/webhooks' });

  // Start server
  try {
    await app.listen({ port: PORT, host: HOST });
    console.log(`Server running at http://${HOST}:${PORT}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

start().catch((err) => {
  console.error(err);
  process.exit(1);
});
