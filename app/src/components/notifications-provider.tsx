import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { applyAcknowledgement, dismissPlugAlerts, isAcknowledged, isNotificationFromThisVisit, isSevere, mergeAcknowledgement, mergeNotification, parseNotification, type Notification } from "@/lib/events";
import { eventStreamUrl } from "@/lib/api-config";
import { useApiConfig } from "@/components/api-config-provider";

type NotificationsState = { items: Notification[]; acknowledged: Notification[]; connection: "connecting" | "live" | "reconnecting"; unread: number; markRead: () => void; clearAll: () => void; dismissAlerts: (plugId: number) => void; updateNotification: (item: Notification) => void };
const NotificationsContext = createContext<NotificationsState | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { baseUrl, ready } = useApiConfig();
  const [items, setItems] = useState<Notification[]>([]);
  const [acknowledged, setAcknowledged] = useState<Notification[]>([]);
  const [connection, setConnection] = useState<NotificationsState["connection"]>("connecting");
  const [readThrough, setReadThrough] = useState(0);
  const dismissed = useRef(new Set<number>());
  useEffect(() => {
    if (!ready) return;
    const startedAt = Date.now(); // Keep this cutoff unchanged on SSE reconnects.
    dismissed.current.clear();
    setItems([]);
    setAcknowledged([]);
    setReadThrough(0);
    setConnection("connecting");
    let source: EventSource | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let lastId: string | null = null; // nothing seen yet: a fresh load asks for new messages only, never history
    let disposed = false;
    const receive = (event: MessageEvent<string>) => {
      const notification = parseNotification(event.data);
      if (notification) {
        lastId = event.lastEventId || String(notification.id);
        if (!isNotificationFromThisVisit(notification, startedAt)) return;
        if (!dismissed.current.has(notification.id)) {
          if (isAcknowledged(notification)) setAcknowledged(current => mergeAcknowledgement(current, notification));
          else if (isSevere(notification)) setAcknowledged(current => current.filter(item => item.plug_id !== notification.plug_id || item.id >= notification.id));
        }
        setItems(current => !dismissed.current.has(notification.id) && isAcknowledged(notification) ? applyAcknowledgement(current, notification) : mergeNotification(current, notification, dismissed.current));
      }
    };
    const connect = () => {
      if (disposed) return;
      const current = new EventSource(eventStreamUrl(baseUrl, lastId));
      source = current;
      current.onopen = () => setConnection("live");
      current.onerror = () => {
        setConnection("reconnecting");
        if (current.readyState === EventSource.CLOSED) {
          current.close();
          retry = setTimeout(connect, 3000);
        }
      };
      current.onmessage = receive;
      current.addEventListener("notification", receive);
      current.addEventListener("new_message", receive);
    };
    connect();
    return () => { disposed = true; if (retry) clearTimeout(retry); source?.close(); };
  }, [baseUrl, ready]);
  const dismissAlerts = (plugId: number) => {
    const latest = items.filter(item => item.plug_id === plugId && isSevere(item)).sort((a, b) => b.id - a.id)[0];
    if (latest) setAcknowledged(current => mergeAcknowledgement(current, { ...latest, resolved_at: new Date().toISOString() }));
    items.filter(item => item.plug_id === plugId && isSevere(item)).forEach(item => dismissed.current.add(item.id));
    setItems(current => dismissPlugAlerts(current, plugId));
  };
  const updateNotification = (item: Notification) => {
    if (item.resolved_at) dismissed.current.add(item.id);
    if (isAcknowledged(item)) {
      items.filter(existing => existing.plug_id === item.plug_id && isSevere(existing) && existing.id <= item.id).forEach(existing => dismissed.current.add(existing.id));
      setAcknowledged(current => mergeAcknowledgement(current, item));
      setItems(current => applyAcknowledgement(current, item));
      return;
    }
    setAcknowledged(current => current.filter(existing => existing.plug_id !== item.plug_id));
    setItems(current => [item, ...current.filter(existing => existing.id !== item.id)].sort((a, b) => b.id - a.id));
  };
  return <NotificationsContext.Provider value={{ items, acknowledged, connection, unread: items.filter(item => item.id > readThrough).length, markRead: () => setReadThrough(items[0]?.id ?? 0), dismissAlerts, updateNotification, clearAll: () => { items.forEach(item => dismissed.current.add(item.id)); setItems([]); setReadThrough(0); } }}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (!context) throw new Error("Notifications provider is missing");
  return context;
}