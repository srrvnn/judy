import { afterEach, describe, expect, it, vi } from "vitest";
import { apiEndpoint, normalizeApiBaseUrl } from "@/lib/api-config";
import { fetchApiPlugs } from "@/lib/api-client";
import { plugsQueryFor } from "@/lib/plugs-query";

afterEach(() => vi.unstubAllGlobals());
describe("Configurable API connection", () => {
  it("uses the replacement base URL for plugs and events", () => {
    expect(apiEndpoint("https://replacement.lhr.life/v1/", "plugs")).toBe("https://replacement.lhr.life/v1/plugs");
    expect(apiEndpoint("https://replacement.lhr.life/", "events")).toBe("https://replacement.lhr.life/v1/events");
  });
  it("rejects unsafe protocols and embedded credentials", () => {
    expect(() => normalizeApiBaseUrl("http://example.com")).toThrow();
    expect(() => normalizeApiBaseUrl("https://user:secret@example.com")).toThrow();
  });
  it("isolates devices from different API URLs", () => {
    expect(plugsQueryFor("https://a.lhr.life").queryKey).not.toEqual(plugsQueryFor("https://b.lhr.life").queryKey);
  });
  it("tests the entered URL and accepts an empty connected server", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await fetchApiPlugs("https://replacement.lhr.life")).toEqual([]);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://replacement.lhr.life/v1/plugs");
  });
  it("fails the connection test for a dead tunnel", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("no tunnel", { status: 502 })));
    await expect(fetchApiPlugs("https://replacement.lhr.life")).rejects.toThrow("HTTP 502");
  });
  it("does not treat a non-plug response as connected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 })));
    await expect(fetchApiPlugs("https://replacement.lhr.life")).rejects.toThrow("valid plug list");
  });
});