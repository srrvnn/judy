import { createServerFn } from "@tanstack/react-start";
import { getRequest } from "@tanstack/react-start/server";
import { createResponsesCall } from "@/lib/ai/responses";

const GATEWAY_URL = "https://ai.gateway.lovable.dev/v1";
const MODEL = "openai/gpt-6-astra";

export type RecommendationInput = {
  alert: string;
  usage: string;
};

export type RecommendationResult =
  | { ok: true; recommendation: string }
  | { ok: false; error: string; retryable: boolean };

const INSTRUCTIONS = [
  "You are Judy, a friendly home energy assistant for a household on Silicon Valley Clean Energy with peak hours from 4pm to 9pm, when electricity costs the most.",
  "The homeowner will describe a socket alert (a device drawing power) and their recent usage details.",
  "Recommend one personalized, practical way to reduce their peak-hour energy costs.",
  "Keep it to 2-4 short sentences: what to do, when to do it, and roughly why it saves money.",
  "Be specific to their device and usage; do not give generic advice.",
  "Do not invent exact dollar figures; speak in relative terms unless the homeowner gave numbers.",
].join(" ");

function userMessage({ alert, usage }: RecommendationInput) {
  return `Socket alert: ${alert}\n\nRecent usage details: ${usage}`;
}

async function callGateway(input: RecommendationInput, request: Request): Promise<string> {
  const apiKey = process.env["LOVABLE_API_KEY"];
  if (!apiKey) throw new Error("AI is not configured yet.");
  const { result } = createResponsesCall(
    request,
    { baseURL: GATEWAY_URL, apiKey, model: MODEL },
    [{ role: "user", content: userMessage(input) }],
    INSTRUCTIONS,
  );
  // Final-answer-only feature: stream the call and consume it server-side.
  const text = (await result.text).trim();
  if (!text) throw new Error("The assistant returned an empty answer.");
  return text;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const getSavingsRecommendation = createServerFn({ method: "POST" })
  .inputValidator((d: RecommendationInput) => {
    const alert = String(d?.alert ?? "").trim();
    const usage = String(d?.usage ?? "").trim();
    if (!alert || !usage) throw new Error("Please describe the alert and your recent usage.");
    return { alert: alert.slice(0, 500), usage: usage.slice(0, 1000) };
  })
  .handler(async ({ data }): Promise<RecommendationResult> => {
    const request = getRequest();
    // One bounded retry for transient rate limits / server errors only.
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const recommendation = await callGateway(data, request);
        return { ok: true, recommendation };
      } catch (error) {
        const status =
          (error as { status?: number; statusCode?: number })?.status ??
          (error as { statusCode?: number })?.statusCode;
        const message = error instanceof Error ? error.message : "Something went wrong.";
        const retryable = status === 429 || (typeof status === "number" && status >= 500);
        if (retryable && attempt === 0) {
          await sleep(1500);
          continue;
        }
        return {
          ok: false,
          error: retryable
            ? "The assistant is busy right now — please try again in a moment."
            : message,
          retryable,
        };
      }
    }
    return { ok: false, error: "The assistant is busy right now — please try again in a moment.", retryable: true };
  });
