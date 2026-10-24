import type { Plug } from "./plugs.functions";
import { isSevere, notificationPlugIds, type Notification } from "./events";

const ONLINE_WINDOW_MS = 120_000;

/** Visit-only colour preview; never creates an executable device action. */
export function previewPlugAlerts(alerts: Notification[], preview: { plugId: number; critical: boolean; name: string } | null): Notification[] {
  if (!preview) return alerts;
  const remaining = alerts.filter(item => item.plug_id !== preview.plugId);
  return preview.critical ? [{ id: -1, plug_id: preview.plugId, kind: "preview", severity: "critical", title: `${preview.name} needs attention`, body: "Critical alert preview", created_at: "", actions: [] }, ...remaining] : remaining;
}

export type PlugStatus = {
  online: number;
  offline: number;
  needsAttention: boolean;
  headline: string;
  detail: string;
};

export function isPlugOnline(plug: Pick<Plug, "last_seen_at">, now = Date.now()) {
  return now - new Date(plug.last_seen_at).getTime() < ONLINE_WINDOW_MS;
}

/**
 * Green ("All is well.") only when every device reported within the last two
 * minutes and no severe or critical notification is outstanding. Anything
 * else — a device that stopped reporting, no devices at all, or a
 * severe/critical alert — is red ("Needs attention.").
 */
export function plugStatus(plugs: Plug[], now = Date.now(), alerts: Notification[] = [], acknowledged: Notification[] = []): PlugStatus {
  const severe = alerts.filter(isSevere);
  const online = plugs.filter((p) => isPlugOnline(p, now)).length;
  const offline = plugs.length - online;
  const needsAttention = plugs.length === 0 || offline > 0 || severe.length > 0;

  const headline =
    plugs.length === 0 ? "Nothing is reporting." : needsAttention ? "Needs attention." : acknowledged.some(item => plugs.some(plug => plug.id === item.plug_id)) ? "Acknowledged" : "All is well.";

  const detail =
    plugs.length === 0
      ? "No devices have checked in yet. Plug one in and it will appear here."
      : severe.length > 0
        ? "" // The alert panel below the device card carries the details.
        : offline > 0
          ? `${offline} of ${plugs.length} ${plugs.length === 1 ? "device is" : "devices are"} offline. Check the ones marked Offline.`
          : headline === "Acknowledged" ? "You chose to ignore the alert. Your device may still be using power." : `All ${plugs.length} devices are behaving and online right now.`;

  return { online, offline, needsAttention, headline, detail };
}

/** Ids of plugs named by a severe or critical notification. */
export function flaggedPlugIds(alerts: Notification[]): Set<number> {
  return new Set(alerts.filter(isSevere).flatMap(notificationPlugIds));
}

/** The most recent severe or critical notification naming a plug, if any. */
export function severeAlertFor(alerts: Notification[], plugId: number): Notification | null {
  let latest: Notification | null = null;
  for (const a of alerts) {
    if (isSevere(a) && notificationPlugIds(a).includes(plugId) && (!latest || a.id > latest.id)) latest = a;
  }
  return latest;
}

/** Plugs named by a severe or critical notification float to the top. */
export function plugsByAttention(plugs: Plug[], alerts: Notification[]): Plug[] {
  const flagged = flaggedPlugIds(alerts);
  return [...plugs].sort((a, b) => Number(flagged.has(b.id)) - Number(flagged.has(a.id)));
}
