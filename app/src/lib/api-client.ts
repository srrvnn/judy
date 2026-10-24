import { z } from "zod";
import { apiEndpoint } from "@/lib/api-config";
import type { Plug } from "@/lib/plugs.functions";
import { parseNotification, type Notification } from "@/lib/events";

const plugSchema = z.object({
  id: z.number().int(), name: z.string().nullable(), last_seen_at: z.string(),
}).passthrough();

export async function fetchApiPlugs(baseUrl: string): Promise<Plug[]> {
  const response = await fetch(apiEndpoint(baseUrl, "plugs"), { signal: AbortSignal.timeout(10000), redirect: "error" });
  if (!response.ok) throw new Error(`Connection failed (HTTP ${response.status}).`);
  const result = z.array(plugSchema).safeParse(await response.json());
  if (!result.success) throw new Error("The server did not return a valid plug list.");
  return result.data as Plug[];
}

export async function renameApiPlug(baseUrl: string, id: number, name: string): Promise<Plug> {
  const input = z.object({ id: z.number().int().positive(), name: z.string().trim().min(1).max(80) }).parse({ id, name });
  const response = await fetch(apiEndpoint(baseUrl, `plugs/${input.id}`), {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.name }), signal: AbortSignal.timeout(10000), redirect: "error",
  });
  if (!response.ok) throw new Error(`Rename failed (HTTP ${response.status}).`);
  return await response.json() as Plug;
}

export async function chooseApiAction(baseUrl: string, actionId: number): Promise<Notification> {
  const id = z.number().int().positive().parse(actionId);
  const response = await fetch(apiEndpoint(baseUrl, `actions/${id}/choose`), {
    method: "POST", signal: AbortSignal.timeout(15000), redirect: "error",
  });
  if (!response.ok) throw new Error(`Action failed (HTTP ${response.status}). Please try again.`);
  const message = parseNotification(await response.text());
  if (!message) throw new Error("The server did not confirm the action.");
  const action = message.actions?.find(item => item.id === id);
  if (!action || action.status === "failed" || !message.resolved_at) {
    throw new Error(action?.result || "The action was not completed. Please try again.");
  }
  return message;
}