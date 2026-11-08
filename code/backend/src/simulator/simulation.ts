
import type { FastifyInstance } from "fastify";

const SIMULATION_SERVICE_URL =
  process.env.SIMULATION_SERVICE_URL ?? "http://127.0.0.1:8000";

export async function registerSimulationRoutes(app: FastifyInstance) {
  app.get("/api/simulations/scenarios", async (_request, reply) => {
    try {
      const response = await fetch(
        `${SIMULATION_SERVICE_URL}/api/simulations/scenarios`,
        { signal: AbortSignal.timeout(10000) }
      );

      const body = await response.json();
      return reply.code(response.status).send(body);
    } catch {
      return reply.code(502).send({
        error: "Simulation service unavailable",
      });
    }
  });

  app.post("/api/simulations", async (request, reply) => {
    try {
      const response = await fetch(
        `${SIMULATION_SERVICE_URL}/api/simulations`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request.body),
          signal: AbortSignal.timeout(30000),
        }
      );

      const body = await response.json();
      return reply.code(response.status).send(body);
    } catch {
      return reply.code(502).send({
        error: "Simulation service unavailable",
      });
    }
  });
}
