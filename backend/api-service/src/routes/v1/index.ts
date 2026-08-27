import { Hono } from "hono";
import authRouter from "../../modules/auth/auth.routes";
import githubRouter from "../../modules/github/github.routes";
import prRouter from "../../modules/pr/pr.routes";

const v1Router = new Hono();

v1Router.route("/auth", authRouter);
v1Router.route("/github", githubRouter);
v1Router.route("/prs", prRouter);

export default v1Router;
