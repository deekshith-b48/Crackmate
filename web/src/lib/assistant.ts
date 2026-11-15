/** Items written through the MCP server are stored with the model name "host": show who really wrote them. */
export const writtenBy = (model?: string | null) => (model === "host" ? "your AI assistant" : (model ?? "").split("/").pop());

/** What to tell someone with no Groq key: their own AI assistant (Claude, Codex) can do it through MCP. */
export const askAssistant = (what: string) => `No Groq key. Ask Claude or Codex: “Use CrackMate to ${what}”.`;
