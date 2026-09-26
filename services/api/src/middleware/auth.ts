import { FastifyReply, FastifyRequest } from 'fastify';

export async function requireAuth(req: FastifyRequest, reply: FastifyReply) {
  try {
    await req.jwtVerify();
  } catch {
    return reply.code(401).send({ error: 'Unauthorised' });
  }
}

export function requireRole(...roles: string[]) {
  return async (req: FastifyRequest, reply: FastifyReply) => {
    const { role } = req.user as { role?: string };
    if (!role || !roles.includes(role)) {
      return reply.code(403).send({ error: 'Forbidden' });
    }
  };
}
