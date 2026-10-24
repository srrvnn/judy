import { z } from "zod";

const actionSchema = z.object({
  id: z.number().int().positive(), label: z.string(), description: z.string(),
  type: z.string(), plug_id: z.number().nullable(), status: z.string(), result: z.string().nullable().optional(),
});

const notificationSchema = z.object({
  id: z.number().int(),
  plug_id: z.number().nullable(),
  kind: z.string(),
  severity: z.string().optional(),
  resolved_at: z.string().nullable().optional(),
  actions: z.array(actionSchema).optional(),
  title: z.string(),
  body: z.string(),
  created_at: z.string(),
});
export type Notification = z.infer<typeof notificationSchema>;

/** A fresh visit ignores history, including history replayed after reconnecting. */
export function isNotificationFromThisVisit(notification: Notification, startedAt: number) {
  return new Date(notification.created_at).getTime() > startedAt;
}

export function parseNotification(data: string): Notification | null {
  try {
    const result = notificationSchema.safeParse(JSON.parse(data));
    if (!result.success) return null;
    if (result.data.kind === "mock") return null;
    return result.data;
  } catch { return null; }
}

const SEVERE_KINDS = new Set(["severe", "critical"]);

export function isSevere(notification: Notification) {
  return !notification.resolved_at && SEVERE_KINDS.has(notification.severity ?? notification.kind);
}

/** Plugs a message concerns: its own plug_id, or the plug named by a turn-off action. */
export function notificationPlugIds(notification: Notification): number[] {
  const ids = notification.plug_id !== null ? [notification.plug_id] : [];
  for (const action of notification.actions ?? []) {
    if (action.type === "turn_off" && action.plug_id !== null && !ids.includes(action.plug_id)) ids.push(action.plug_id);
  }
  return ids;
}

export function notificationAction(notification: Notification, type: "turn_off" | "dismiss") {
  return notification.actions?.find(action => (action.type === type || (type === "dismiss" && action.type === "ignore")) && (action.plug_id === notification.plug_id || (notification.plug_id === null && action.plug_id !== null)) && (action.status === "suggested" || action.status === "failed"));
}

export function isAcknowledged(notification: Notification) {
  return Boolean(notification.resolved_at && notification.actions?.some(action =>
    action.plug_id === notification.plug_id && (action.type === "dismiss" || action.type === "ignore") && action.status === "done",
  ));
}

export function mergeAcknowledgement(items: Notification[], incoming: Notification) {
  if (items.some(item => item.plug_id === incoming.plug_id && item.id > incoming.id)) return items;
  return [incoming, ...items.filter(item => item.plug_id !== incoming.plug_id)];
}

export function applyAcknowledgement(items: Notification[], incoming: Notification) {
  return [incoming, ...items.filter(item => item.id !== incoming.id && !(item.plug_id === incoming.plug_id && item.id <= incoming.id && isSevere(item)))].sort((a, b) => b.id - a.id);
}

export function dismissPlugAlerts(items: Notification[], plugId: number) {
  return items.filter(item => item.plug_id !== plugId || !isSevere(item));
}

export function mergeNotification(items: Notification[], incoming: Notification, dismissed: ReadonlySet<number> = new Set()) {
  if (dismissed.has(incoming.id)) return items;
  return [incoming, ...items.filter(item => item.id !== incoming.id)]
    .sort((a, b) => b.id - a.id);
}