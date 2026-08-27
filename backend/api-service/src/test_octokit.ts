import { getOctokitApp } from "./modules/github/github-app.service";

try {
  const app = getOctokitApp();
  console.log("✅ Octokit App initialized cleanly without OpenSSL errors!");
} catch (e: any) {
  console.error("❌ Error initializing Octokit App:", e.message);
}
