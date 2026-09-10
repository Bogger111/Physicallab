import { Container, getContainer } from "@cloudflare/containers";

export class PhysicsLabContainer extends Container {
  defaultPort = 8001;
  sleepAfter = "10m";
}

interface Env {
  PHYSICSLAB_CONTAINER: DurableObjectNamespace<PhysicsLabContainer>;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = getContainer(env.PHYSICSLAB_CONTAINER, "physicslab-api");
    return container.fetch(request);
  },
};
