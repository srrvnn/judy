import { describe, expect, it } from "vitest";

import { isPlugOnline, plugStatus, plugsByAttention, previewPlugAlerts, severeAlertFor } from "@/lib/status";

const NOW = new Date("2026-10-24T20:40:00Z").getTime();
const seen = (secondsAgo: number) => new Date(NOW - secondsAgo * 1000).toISOString();

const plug = (id: number, secondsAgo: number) =>
  ({
    id,
    household_id: 1,
    device_id: `d${id}`,
    name: null,
    model: "EP25",
    host: "192.168.1.5",
    room: null,
    has_energy: true,
    first_seen_at: seen(9999),
    last_seen_at: seen(secondsAgo),
  }) as never;

describe("Plug status colour rule", () => {
  it("previews critical red and non-critical green without executable actions", () => {
    const critical = previewPlugAlerts([], { plugId: 1, critical: true, name: "Laptop" });
    expect(plugStatus([plug(1, 10)], NOW, critical).needsAttention).toBe(true);
    expect(critical[0]?.actions).toEqual([]);
    expect(plugStatus([plug(1, 10)], NOW, previewPlugAlerts(critical, { plugId: 1, critical: false, name: "Laptop" })).needsAttention).toBe(false);
    expect(previewPlugAlerts(critical, null)).toEqual(critical);
  });
  it("shows acknowledgement after dismissal but new critical alerts override it", () => {
    const acknowledgement = { id: 8, plug_id: 1, kind: "power_after_off", severity: "critical", title: "Laptop alert", body: "Drawing power", created_at: seen(5), resolved_at: seen(1) };
    expect(plugStatus([plug(1, 10)], NOW, [], [acknowledgement]).needsAttention).toBe(false);
    expect(plugStatus([plug(1, 10)], NOW, [{ ...acknowledgement, id: 9, resolved_at: null }], [acknowledgement]).needsAttention).toBe(true);
    expect(plugStatus([plug(1, 300)], NOW, [], [acknowledgement]).needsAttention).toBe(true);
  });
  it("is green when every device reported in the last two minutes", () => {
    const s = plugStatus([plug(1, 10), plug(2, 90)], NOW);

    expect(s.needsAttention).toBe(false);
    expect(s.headline).toBe("All is well.");
    expect(s.detail).toBe("All 2 devices are behaving and online right now.");
  });

  it("is red when one device of two stopped reporting", () => {
    const s = plugStatus([plug(1, 10), plug(2, 300)], NOW);

    expect(s.needsAttention).toBe(true);
    expect(s.headline).toBe("Needs attention.");
    expect(s.detail).toBe("1 of 2 devices are offline. Check the ones marked Offline.");
    expect(s.offline).toBe(1);
  });

  it("is red when there are no devices at all", () => {
    const s = plugStatus([], NOW);

    expect(s.needsAttention).toBe(true);
    expect(s.headline).toBe("Nothing is reporting.");
  });

  it("counts a device offline once two minutes have passed", () => {
    expect(isPlugOnline({ last_seen_at: seen(119) }, NOW)).toBe(true);
    expect(isPlugOnline({ last_seen_at: seen(121) }, NOW)).toBe(false);
  });

  const alert = (id: number, plugId: number | null, kind = "severe") =>
    ({ id, plug_id: plugId, kind, title: "Laptop is overheating", body: "...", created_at: seen(5) }) as never;

  it("is red when a severe alert targets an online device", () => {
    const s = plugStatus([plug(1, 10)], NOW, [alert(1, 1)]);

    expect(s.needsAttention).toBe(true);
    expect(s.headline).toBe("Needs attention.");
    expect(s.detail).toBe("");
  });

  it("flags the plug named by a turn-off action when the message omits plug_id", () => {
    const powerDown = {
      id: 13, plug_id: null, kind: "afternoon_power_down", severity: "critical",
      title: "It's 4 pm, time to power down", body: "...", created_at: seen(5),
      actions: [{ id: 25, type: "turn_off", label: "Turn off Laptop", description: "", plug_id: 1, status: "suggested", result: null }],
    } as never;
    expect(plugStatus([plug(1, 10)], NOW, [powerDown]).needsAttention).toBe(true);
    expect(plugsByAttention([plug(1, 10)], [powerDown]).map(p => p.id)).toEqual([1]);
  });

  it("stays green for ordinary notifications", () => {
    const s = plugStatus([plug(1, 10)], NOW, [alert(1, 1, "update")]);

    expect(s.needsAttention).toBe(false);
  });

  it("moves the alerted device to the top of the list", () => {
    const ordered = plugsByAttention([plug(1, 10), plug(2, 10), plug(3, 10)], [alert(1, 3)]);

    expect(ordered.map((p) => p.id)).toEqual([3, 1, 2]);
  });

  it("picks the most recent severe alert for a flagged device", () => {
    expect(severeAlertFor([alert(1, 3), alert(2, 3, "critical")], 3)?.id).toBe(2);
    expect(severeAlertFor([alert(1, 3)], 1)).toBeNull();
    expect(severeAlertFor([alert(1, 3, "update")], 3)).toBeNull();
  });
  it("turns red and prioritizes Laptop for a critical API severity", () => {
    const critical = { id: 8, plug_id: 2, kind: "power_after_off", severity: "critical", title: "Laptop just started drawing power", body: "Laptop was off and is now drawing 12W.", created_at: seen(5) };
    expect(plugStatus([plug(1, 10), plug(2, 10)], NOW, [critical]).needsAttention).toBe(true);
    expect(plugsByAttention([plug(1, 10), plug(2, 10)], [critical]).map(p => p.id)).toEqual([2, 1]);
    expect(severeAlertFor([critical], 2)?.id).toBe(8);
    expect(plugStatus([plug(1, 10), plug(2, 10)], NOW, [{ ...critical, resolved_at: seen(1) }]).needsAttention).toBe(false);
  });
});
