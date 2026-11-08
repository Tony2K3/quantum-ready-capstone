import Fastify from "fastify";

import { registerSimulationRoutes } from "./simulation";

const app = Fastify({ logger: true });

app.register(registerSimulationRoutes);
app.get("/health", async () => ({ status: "ok", service: "quantinnel-api" }));

const port = Number(process.env.PORT ?? 3001);
const host = process.env.HOST ?? "0.0.0.0";

app
  .listen({ port, host })
  .catch((err) => {
    app.log.error(err);
    process.exit(1);
  });
