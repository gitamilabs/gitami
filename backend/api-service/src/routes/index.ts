import { Hono } from "hono";
import v1Router from "./v1";

const apiRouter = new Hono();

// Mount v1Router under both /v1 and / to support /api/v1/* and /api/* endpoints
apiRouter.route("/v1", v1Router);
apiRouter.route("/", v1Router);

export default apiRouter;
