import { describe, expect, it } from "vitest";
import { applyAcknowledgement, dismissPlugAlerts, isAcknowledged, isNotificationFromThisVisit, isSevere, mergeAcknowledgement, mergeNotification, notificationAction, parseNotification } from "@/lib/events";

const message = { id: 1, plug_id: 1, kind: "update", title: "Laptop", body: "Update received", created_at: "2026-10-24T21:00:00Z" };
describe("Live notifications", () => {
  const startedAt = Date.parse("2026-10-24T23:21:00Z");
  it("ignores alerts and acknowledgements created before a fresh load", () => {
    expect(isNotificationFromThisVisit({ ...message, severity: "critical", created_at: "2026-10-24T23:20:59Z" }, startedAt)).toBe(false);
    expect(isNotificationFromThisVisit({ ...message, resolved_at: "2026-10-24T23:21:01Z", created_at: "2026-10-24T23:20:59Z" }, startedAt)).toBe(false);
    expect(isNotificationFromThisVisit({ ...message, created_at: "2026-10-24T23:21:00Z" }, startedAt)).toBe(false);
  });
  it("accepts new critical alerts after load and rejects old reconnect replays", () => {
    expect(isNotificationFromThisVisit({ ...message, severity: "critical", created_at: "2026-10-24T23:21:01Z" }, startedAt)).toBe(true);
    expect(isNotificationFromThisVisit(message, startedAt)).toBe(false);
  });
  const ignoreAction = { id: 16, type: "ignore", label: "Ignore", description: "Ignore alert", plug_id: 1, status: "done" };
  const acknowledged = { ...message, id: 3, severity: "critical", resolved_at: "2026-10-24T22:38:00Z", actions: [ignoreAction] };
  it("acknowledges a confirmed Ignore action but not a failed or power-off action", () => {
    expect(isAcknowledged(acknowledged)).toBe(true);
    expect(isAcknowledged({ ...acknowledged, actions: [{ ...ignoreAction, status: "failed" }] })).toBe(false);
    expect(isAcknowledged({ ...acknowledged, actions: [{ ...ignoreAction, type: "turn_off" }] })).toBe(false);
  });
  it("accepts Ignore as a server-provided dismissal action", () => {
    expect(notificationAction({ ...acknowledged, actions: [{ ...ignoreAction, status: "suggested" }] }, "dismiss")?.id).toBe(16);
  });
  it("acknowledges older alerts without swallowing a newer critical event", () => {
    const newer = { ...message, id: 4, severity: "critical" };
    expect(applyAcknowledgement([{ ...message, id: 2, severity: "critical" }, newer], acknowledged).map(item => item.id)).toEqual([4, 3]);
    expect(mergeAcknowledgement([{ ...acknowledged, id: 5 }], acknowledged)[0]?.id).toBe(5);
  });
  it("parses a server message", () => {
    expect(parseNotification(JSON.stringify(message))).toEqual(message);
  });
  it("ignores malformed data and heartbeat payloads", () => {
    expect(parseNotification("ping")).toBeNull();
    expect(parseNotification('{"id":1}')).toBeNull();
  });
  it("ignores the mock heater message", () => {
    const mock = { ...message, kind: "mock", title: "Mock: heater left on" };
    expect(parseNotification(JSON.stringify(mock))).toBeNull();
  });
  it("deduplicates replayed events", () => {
    expect(mergeNotification([message], message)).toHaveLength(1);
  });
  it("puts newest message first", () => {
    expect(mergeNotification([message], { ...message, id: 2 }).map(item => item.id)).toEqual([2, 1]);
  });
  it("flags only severe and critical kinds as severe", () => {
    expect(isSevere({ ...message, kind: "severe" })).toBe(true);
    expect(isSevere({ ...message, kind: "critical" })).toBe(true);
    expect(isSevere({ ...message, kind: "update" })).toBe(false);
  });
  it("dismisses severe and critical alerts only for the selected plug", () => {
    const items = [
      { ...message, id: 2, kind: "severe" },
      { ...message, id: 3, kind: "critical" },
      { ...message, id: 4, kind: "critical", plug_id: 2 },
      message,
    ];
    expect(dismissPlugAlerts(items, 1).map(item => item.id)).toEqual([4, 1]);
  });
  it("ignores dismissed replay but allows a new critical alert", () => {
    const dismissed = new Set([1]);
    expect(mergeNotification([], { ...message, kind: "critical" }, dismissed)).toEqual([]);
    expect(mergeNotification([], { ...message, id: 2, kind: "critical" }, dismissed).map(item => item.id)).toEqual([2]);
  });
  it("uses API severity even when the notification kind describes power usage", () => {
    expect(isSevere({ ...message, kind: "power_after_off", severity: "severe" })).toBe(true);
    expect(isSevere({ ...message, kind: "power_after_off", severity: "critical" })).toBe(true);
    expect(isSevere({ ...message, kind: "critical", severity: "info" })).toBe(false);
  });
  it("resolved critical alerts no longer need attention", () => {
    expect(isSevere({ ...message, severity: "critical", resolved_at: "2026-10-24T22:30:00Z" })).toBe(false);
  });
  it("preserves the server-provided turn off and dismiss action IDs", () => {
    const actions = [
      { id: 15, type: "turn_off", label: "Turn off", description: "Switch Laptop off", plug_id: 1, status: "suggested", result: null },
      { id: 16, type: "dismiss", label: "Dismiss", description: "Ignore this", plug_id: 1, status: "suggested", result: null },
    ];
    const parsed = parseNotification(JSON.stringify({ ...message, severity: "critical", actions }));
    expect(parsed?.actions).toEqual(actions);
    if (!parsed) throw new Error("Expected valid notification");
    expect(notificationAction(parsed, "turn_off")?.id).toBe(15);
    expect(notificationAction(parsed, "dismiss")?.id).toBe(16);
  });
});