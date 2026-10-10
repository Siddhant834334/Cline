import { Agent } from "@cline/sdk";
const agent = new Agent({
  providerId: "anthropic",
  modelId: process.env.FNN_MODEL || "claude-3-5-haiku-latest",
  apiKey: process.env.ANTHROPIC_API_KEY,
  systemPrompt: "Reply with the single word: pong",
  tools: [],
});
const r = await agent.run("ping");
const ok = r.status !== "failed" && !r.error && r.outputText.length > 0;
console.log(JSON.stringify({ ok, status: r.status, output: r.outputText, error: r.error ? String(r.error.message || r.error) : null }));
process.exitCode = ok ? 0 : 1;
