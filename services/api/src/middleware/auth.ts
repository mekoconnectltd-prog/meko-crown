import { FastifyRequest, FastifyReply } from 'fastify';

export async function requireAuth(req: FastifyRequest, reply: FastifyReply) {
  try {
    await req.jwtVerify();
  } catch {
    return reply.code(401).send({ error: 'Unauthorised' });
  }
}

export function requireRole(...roles: string[]) {
  return async (req: FastifyRequest, reply: FastifyReply) => {
    const user = req.user as { role?: string };
    if (!user.role || !roles.includes(user.role)) {
      return reply.code(403).send({ error: 'Forbidden' });
    }
  };
}
