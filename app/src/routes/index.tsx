import { createFileRoute, ClientOnly } from "@tanstack/react-router";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Check, Pencil, Power, X } from "lucide-react";
import { useServerFn } from "@tanstack/react-start";
import { useApiConfig } from "@/components/api-config-provider";
import { DEFAULT_API_BASE_URL } from "@/lib/api-config";
import { chooseApiAction, renameApiPlug } from "@/lib/api-client";
import { notificationAction, type Notification } from "@/lib/events";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { renamePlug, type Plug } from "@/lib/plugs.functions";
import { flaggedPlugIds, isPlugOnline, plugStatus, plugsByAttention, previewPlugAlerts, severeAlertFor } from "@/lib/status";
import { plugsQuery, plugsQueryFor } from "@/lib/plugs-query";
import { ApiBreakScreen } from "@/components/api-break";
import { useNotifications } from "@/components/notifications-provider";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Judy — Your sockets" },
      { name: "description", content: "Live view of every smart plug in your home, pulled from the Judy server." },
      { property: "og:title", content: "Judy — Your sockets" },

      { property: "og:description", content: "Live view of every smart plug in your home." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  loader: ({ context }) => context.queryClient.ensureQueryData(plugsQuery),
  component: Index,
  errorComponent: ApiBreakScreen,
});

function ago(iso: string) {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s} seconds ago`;
  if (s < 3600) return `${Math.round(s / 60)} minutes ago`;
  return `${Math.round(s / 3600)} hours ago`;
}

function Index() {
  const { baseUrl } = useApiConfig();
  const { data: plugs, isError } = useSuspenseQuery(plugsQueryFor(baseUrl));
  const { items: liveNotifications, acknowledged } = useNotifications();
  const [preview, setPreview] = useState<{ plugId: number; critical: boolean; name: string } | null>(null);
  const notifications = previewPlugAlerts(liveNotifications, preview);
  if (isError || plugs === null) return <ApiBreakScreen />;
  const { needsAttention, headline, detail } = plugStatus(plugs, Date.now(), notifications, acknowledged);
  const flagged = flaggedPlugIds(notifications);
  const ordered = plugsByAttention(plugs, notifications);
  const newest = plugs.reduce<string | null>(
    (acc, p) => (!acc || new Date(p.last_seen_at) > new Date(acc) ? p.last_seen_at : acc),
    null,
  );

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col bg-background">
      <header className="flex items-center justify-between px-5 pb-2 pt-5">
        <h1 className="font-serif text-3xl font-bold italic text-primary">Judy</h1>
      </header>

      <main className="flex-1 px-5 pb-28">
        <section
          className={`mt-3 rounded-lg px-4 py-4 ${
            needsAttention ? "bg-destructive text-destructive-foreground" : "bg-primary text-primary-foreground"
          }`}
        >
          <h2 className="font-display text-2xl font-semibold">{headline}</h2>
          {detail && (
            <p
              className={`mt-2 text-sm leading-relaxed ${
                needsAttention ? "text-destructive-foreground/90" : "text-primary-foreground/90"
              }`}
            >
              {detail}
            </p>
          )}
          <hr
            className={`mt-3 ${
              needsAttention ? "border-destructive-foreground/25" : "border-primary-foreground/25"
            }`}
          />
          <p
            className={`mt-3 text-[10px] ${
              needsAttention ? "text-destructive-foreground/75" : "text-primary-foreground/75"
            }`}
          >
            <ClientOnly fallback="Checking latest report…">{newest ? `Last updated ${ago(newest)}` : "Waiting for the first report"}</ClientOnly>
          </p>
        </section>

        {plugs.length === 0 ? (
          <p className="mt-10 text-muted-foreground">No plugs found yet. Plug one in and it will appear here.</p>
        ) : (
          <section className="mt-4 space-y-3">
            {ordered.map((p) => {
              const alert = severeAlertFor(notifications, p.id);
              return (
                <PlugCard key={p.id} plug={p} flagged={flagged.has(p.id)} alert={alert} acknowledged={acknowledged.find(item => item.plug_id === p.id) ?? null} onSavePreview={(critical, name) => setPreview({ plugId: p.id, critical, name })} />
              );
            })}
          </section>
        )}
      </main>

    </div>
  );
}

function PlugCard({ plug, flagged = false, alert, acknowledged, onSavePreview }: { plug: Plug; flagged?: boolean; alert: Notification | null; acknowledged: Notification | null; onSavePreview: (critical: boolean, name: string) => void }) {
  const { baseUrl } = useApiConfig();
  const rename = useServerFn(renamePlug);
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(plug.name ?? "");
  const [critical, setCritical] = useState(flagged);
  const isOnline = isPlugOnline(plug);
  const m = useMutation({
    mutationFn: (n: string) => n === plug.name ? Promise.resolve(plug) : baseUrl === DEFAULT_API_BASE_URL ? rename({ data: { id: plug.id, name: n } }) : renameApiPlug(baseUrl, plug.id, n),
    onSuccess: (saved) => {
      onSavePreview(critical, saved.name ?? name);
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["plugs"] });
    },
  });

  return (
    <article
      className="relative"
    >
      <div className={`group relative z-10 rounded-lg px-4 py-4 ${!isOnline ? "bg-destructive/5" : "bg-card"}`}>
      {editing ? (
        <form className="space-y-4" onSubmit={e => { e.preventDefault(); if (name.trim()) m.mutate(name.trim()); }}>
          <label className="block text-xs font-medium" htmlFor={`name-${plug.id}`}>Device name</label>
          <Input id={`name-${plug.id}`} autoFocus value={name} maxLength={80} onChange={e => setName(e.target.value)} required />
          <div className="flex items-center justify-between">
            <label htmlFor={`critical-${plug.id}`} className="text-sm">{critical ? "Critical" : "Non-critical"}</label>
            <Switch id={`critical-${plug.id}`} aria-label="Critical alert preview" checked={critical} onCheckedChange={setCritical} className="data-[state=checked]:bg-destructive" />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" disabled={m.isPending} onClick={() => setEditing(false)}>Cancel</Button>
            <Button type="submit" size="sm" disabled={m.isPending || !name.trim()}>{m.isPending ? "Saving…" : "Save"}</Button>
          </div>
        </form>
      ) : (
        <Button variant="ghost" aria-label={`Edit ${plug.name ?? "Laptop"}`} onClick={() => { setName(plug.name ?? ""); setCritical(flagged); m.reset(); setEditing(true); }} className="h-auto w-full justify-between gap-3 whitespace-normal p-0 text-left hover:bg-transparent">
          <span className="flex min-w-0 items-center gap-2"><h3 className="break-words text-sm font-semibold text-foreground">{plug.name ?? "Unnamed plug"}</h3><Pencil className="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100" /></span>
          <span className={`shrink-0 text-xs font-bold ${flagged || !isOnline ? "text-destructive" : "text-primary"}`}>
            {flagged ? "Critical" : acknowledged ? "Acknowledged" : isOnline ? "Online" : "Offline"}
          </span>
        </Button>
      )}
      </div>
      {alert?.kind === "preview" ? <div className="mt-3 rounded-lg bg-destructive/10 p-4 text-sm font-semibold text-destructive">{alert.title}</div> : alert ? <AlertActions key={alert.id} alert={alert} plugId={plug.id} name={plug.name ?? "Unnamed plug"} /> : acknowledged && <AcknowledgedPanel alert={acknowledged} name={plug.name ?? "Unnamed plug"} />}
      {m.isError && <p className="mt-2 text-xs text-destructive">{m.error.message}</p>}
    </article>
  );
}

function AlertActions({ alert, plugId, name }: { alert: Notification; plugId: number; name: string }) {
  const { baseUrl } = useApiConfig();
  const { updateNotification, dismissAlerts } = useNotifications();
  const qc = useQueryClient();
  const turnOff = notificationAction(alert, "turn_off");
  const dismiss = notificationAction(alert, "dismiss");
  const action = useMutation({
    mutationFn: (id: number) => chooseApiAction(baseUrl, id),
    onSuccess: message => {
      updateNotification(message);
      qc.invalidateQueries({ queryKey: ["plugs"] });
    },
  });
  const headline = alert.kind === "afternoon_power_down" ? `${name} is drawing power at peak hours` : `${name} needs attention`;
  return (
    <div className="relative mt-3 rounded-2xl bg-destructive/10 px-4 py-5 text-foreground before:absolute before:-top-5 before:left-1/2 before:h-5 before:w-px before:bg-destructive/20" aria-label="Laptop alert actions">
      <h4 className="font-display text-lg font-bold leading-snug">{headline}</h4>
      <p className="mt-2 text-sm leading-relaxed text-foreground">Consider turning it off to save $1.</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Button variant="outline" className="h-11 rounded-full bg-card px-5 font-display text-xs font-bold uppercase tracking-wide text-foreground shadow-sm" disabled={!turnOff || action.isPending} onClick={() => { if (turnOff) action.mutate(turnOff.id); }}>
          <Power />{action.isPending && action.variables === turnOff?.id ? "Turning off…" : "Turn off"}
        </Button>
        <Button variant="outline" className="h-11 rounded-full bg-card px-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground" disabled={action.isPending} onClick={() => dismiss ? action.mutate(dismiss.id) : dismissAlerts(plugId)}>
          <X />{action.isPending && action.variables === dismiss?.id ? "Dismissing…" : "Dismiss"}
        </Button>
      </div>
      {!turnOff && <p className="mt-3 text-xs text-muted-foreground">The server hasn’t offered a Turn off action for this alert.</p>}
      {action.isError && <p role="alert" className="mt-3 text-sm text-destructive">{action.error.message}</p>}
      <p className="mt-4 text-xs text-muted-foreground"><ClientOnly fallback="Just updated">Last updated {ago(alert.created_at)}</ClientOnly></p>
    </div>
  );
}


function AcknowledgedPanel({ alert, name }: { alert: Notification; name: string }) {
  return (
    <div className="relative mt-3 rounded-lg bg-primary/10 px-4 py-4 before:absolute before:-top-5 before:left-1/2 before:h-5 before:w-px before:bg-primary/20" aria-label={`${name} acknowledged alert`}>
      <h4 className="font-display text-base font-semibold">You chose to ignore the {name} alert</h4>
      <p className="mt-3 text-sm leading-relaxed">{alert.body}</p>
      <p className="mt-2 text-sm text-muted-foreground">The alert is acknowledged. This does not turn the device off.</p>
      <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground"><Check size={16} /> Acknowledged</div>
      <p className="mt-3 text-xs text-muted-foreground">Decided by you · <ClientOnly fallback="Just updated">{ago(alert.resolved_at ?? alert.created_at)}</ClientOnly></p>
    </div>
  );
}
