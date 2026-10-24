import { beforeEach, describe, expect, it, vi } from "vitest";
import { listPlugs } from "@/lib/plugs.functions";
import { plugsQuery } from "@/lib/plugs-query";

vi.mock("@/lib/plugs.functions", () => ({ listPlugs: vi.fn() }));

describe("API availability", () => {
  beforeEach(() => vi.resetAllMocks());
  it("returns an unavailable state when the API fails", async () => {
    vi.mocked(listPlugs).mockRejectedValue(new Error("API down"));
    const run = plugsQuery.queryFn;
    if (typeof run !== "function") throw new Error("Missing query");
    expect(await run({} as Parameters<typeof run>[0])).toBeNull();
  });
  it("distinguishes an available empty API from downtime", async () => {
    vi.mocked(listPlugs).mockResolvedValue([]);
    const run = plugsQuery.queryFn;
    if (typeof run !== "function") throw new Error("Missing query");
    expect(await run({} as Parameters<typeof run>[0])).toEqual([]);
  });
});