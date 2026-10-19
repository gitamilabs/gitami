import { Hono } from "hono";
import authRouter from "../../modules/auth/auth.routes";
import githubRouter from "../../modules/github/github.routes";
import prRouter from "../../modules/pr/pr.routes";
import teamsRouter from "../../modules/teams/teams.routes";
import projectsRouter from "../../modules/projects/projects.routes";
import buildsRouter from "../../modules/builds/builds.routes";
import intelligenceRouter from "../../modules/intelligence/intelligence.routes";

const v1Router = new Hono();

v1Router.route("/auth", authRouter);
v1Router.route("/github", githubRouter);
v1Router.route("/prs", prRouter);
v1Router.route("/teams", teamsRouter);
v1Router.route("/projects", projectsRouter);
v1Router.route("/builds", buildsRouter);
v1Router.route("/intelligence", intelligenceRouter);

export default v1Router;

