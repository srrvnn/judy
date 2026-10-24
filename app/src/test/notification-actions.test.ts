import { afterEach, describe, expect, it, vi } from "vitest";
import { chooseApiAction } from "@/lib/api-client";

const message = {
  id: 8, plug_id: 1, kind: "power_after_off", severity: "critical", title: "Laptop", body: "Drawing power", created_at: "2026-10-24T22:29:19Z", resolved_at: "2026-10-24T22:31:00Z",
  actions: [{ id: 15, type: "turn_off", label: "Turn off", description: "Switch Laptop off", plug_id: 1, status: "done", result: "Switched off" }],
};
afterEach(() => vi.unstubAllGlobals());
describe("Notification action requests", () => {
  it("posts the server-provided action ID and returns its confirmed result", async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(message)));
    vi.stubGlobal("fetch", request);
    expect((await chooseApiAction("https://example.com", 15)).resolved_at).toBe(message.resolved_at);
    expect(request).toHaveBeenCalledWith("https://example.com/v1/actions/15/choose", expect.objectContaining({ method: "POST" }));
  });
  it("does not confirm a failed power action", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...message, resolved_at: null, actions: [{ ...message.actions[0], status: "failed", result: "Plug unreachable" }] }))));
    await expect(chooseApiAction("https://example.com", 15)).rejects.toThrow("Plug unreachable");
  });
  it("does not confirm an unresolved action", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...message, resolved_at: null }))));
    await expect(chooseApiAction("https://example.com", 15)).rejects.toThrow("Switched off");
  });
});