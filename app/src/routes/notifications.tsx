import { createFileRoute } from "@tanstack/react-router";
import { Bell, CheckCheck, Radio, BellOff, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNotifications } from "@/components/notifications-provider";

export const Route = createFileRoute("/notifications")({
  head: () => ({ meta: [
    { title: "Judy — Live notifications" },
    { name: "description", content: "Live notifications from your Judy plug server." },
    { property: "og:title", content: "Judy — Live notifications" },
    { property: "og:description", content: "Updates from your connected devices, as they happen." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: Notifications,
});

function Notifications() {
  const { items, connection, unread, markRead, clearAll } = useNotifications();
  return <div className="mx-auto min-h-dvh max-w-md px-6 pb-28 pt-8">
    <header className="flex items-center justify-between gap-3">
      <h1 className="font-display text-5xl font-semibold text-primary">Judy</h1>
      <span role="status" className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold ${connection === "reconnecting" ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary"}`}>
        <Radio className="size-3.5" />{connection === "live" ? "Live" : connection === "connecting" ? "Connecting…" : "Reconnecting…"}
      </span>
    </header>
    <main className="mt-8">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-2xl font-semibold">Notifications</h2>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" title="Mark all as read" aria-label="Mark all as read" onClick={markRead} disabled={unread === 0} className="text-primary"><CheckCheck className="!size-5" /></Button>
          <Button variant="ghost" size="icon" title="Clear all notifications" aria-label="Clear all notifications" onClick={clearAll} disabled={items.length === 0} className="text-destructive"><Trash2 className="!size-5" /></Button>
        </div>
      </div>
      {connection === "reconnecting" && <p role="alert" className="mb-5 text-sm text-destructive">The live connection was interrupted. Retrying automatically.</p>}
      {items.length === 0 ? <div className="flex flex-col items-center py-16 text-center">
        <BellOff className="mb-5 size-10 text-muted-foreground" strokeWidth={1.5} />
        <h3 className="font-display text-xl font-medium">No notifications yet</h3>
      </div> : <section aria-label="Notifications" aria-live="polite" className="space-y-4">
        {items.map(item => <article key={item.id} className="rounded-lg bg-card p-5 shadow-[var(--shadow-card)]">
          <div className="flex items-start gap-3">
            <Bell className="mt-0.5 size-5 shrink-0 text-primary" />
            <div className="min-w-0">
              <h3 className="break-words font-semibold">{item.title}</h3>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">{item.body}</p>
              <time dateTime={item.created_at} className="mt-3 block text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</time>
            </div>
          </div>
        </article>)}
      </section>}
    </main>
  </div>;
}