import { createServerFn } from "@tanstack/react-start";
import { DEFAULT_API_BASE_URL } from "@/lib/api-config";

const API = `${DEFAULT_API_BASE_URL}/v1`;

export type Plug = {
  id: number;
  household_id: number;
  device_id: string;
  name: string | null;
  model: string;
  host: string;
  room: string | null;
  has_energy: boolean;
  first_seen_at: string;
  last_seen_at: string;
};

export const listPlugs = createServerFn({ method: "GET" }).handler(async () => {
  const res = await fetch(`${API}/plugs`);
  if (!res.ok) throw new Error(`Plug server returned ${res.status}`);
  return (await res.json()) as Plug[];
});

export const renamePlug = createServerFn({ method: "POST" })
  .inputValidator((d: { id: number; name: string }) => {
    const name = String(d.name ?? "").trim();
    if (!Number.isInteger(d.id) || !name) throw new Error("Invalid input");
    return { id: d.id, name: name.slice(0, 80) };
  })
  .handler(async ({ data }) => {
    const res = await fetch(`${API}/plugs/${data.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: data.name }),
    });
    if (!res.ok) throw new Error(`Rename failed (${res.status})`);
    return (await res.json()) as Plug;
  });
