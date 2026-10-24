import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { useApiConfig } from "@/components/api-config-provider";
import { DEFAULT_API_BASE_URL } from "@/lib/api-config";
import { renameApiPlug } from "@/lib/api-client";
import { ChevronRight, Laptop, Plus, Video, ArrowLeft, ArrowRight, PlugZap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { plugsQueryFor } from "@/lib/plugs-query";
import { renamePlug, type Plug } from "@/lib/plugs.functions";
import { isPlugOnline } from "@/lib/status";
import { ApiBreakBox, ApiBreakScreen } from "@/components/api-break";

export const Route = createFileRoute("/profile")({
  head: () => ({ meta: [
    { title: "Judy — Profile & plugs" },
    { name: "description", content: "Your Judy profile, electricity plan and connected Laptop plug." },
    { property: "og:title", content: "Judy — Profile & plugs" },
    { property: "og:description", content: "Your profile and connected plugs, together in Judy." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: Profile,
  errorComponent: ApiBreakScreen,
});

function Profile() {
  const [rateOpen, setRateOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  return (
    <div className="mx-auto min-h-dvh max-w-md px-6 pb-28 pt-8">
      <header className="flex items-center justify-between">
        <h1 className="font-display text-5xl font-semibold text-primary">Judy</h1>
        <span className="rounded-full bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">Profile</span>
      </header>
      <main className="mt-8">
        <h2 className="mb-5 font-display text-2xl font-semibold">Profile & plugs</h2>
        <div className="rounded-lg bg-card px-4 py-4 shadow-[var(--shadow-card)]">
          <InfoRow label="Name" value="Not set" />
        </div>
        <div className="mt-5 rounded-lg bg-card px-4 shadow-[var(--shadow-card)]">
          <InfoRow label="Provider" value="Silicon Valley Clean Energy" />
          <InfoRow label="Rate plan" value="Time-of-use (example)" />
          <InfoRow label="Peak hours" value="4–9pm" />

          <Button variant="ghost" onClick={() => setRateOpen(true)} className="h-auto min-h-14 w-full justify-between whitespace-normal px-0 text-left text-primary">
            Understand your rate plan <Video className="!size-5" />
          </Button>
        </div>
        <section aria-label="Your plugs" className="mt-5 rounded-lg bg-card px-4 shadow-[var(--shadow-card)]">
          <ConnectedPlugs />
          <Button variant="ghost" onClick={() => setAddOpen(true)} className="h-14 w-full justify-between px-0 text-primary">
            Add new plug <Plus className="!size-5" />
          </Button>
        </section>
        <Button variant="outline" disabled title="No account is signed in" className="mt-5 h-11 w-full rounded-full bg-card text-muted-foreground">Sign out</Button>
      </main>
      <RateGuide open={rateOpen} onOpenChange={setRateOpen} />
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-[calc(100%-3rem)] rounded-lg sm:max-w-sm">
          <PlugZap className="size-8 text-primary" />
          <DialogTitle>Add a plug</DialogTitle>
          <DialogDescription>Connect your new plug to the Judy server. Once it reports, it will appear here automatically.</DialogDescription>
          <Button onClick={() => setAddOpen(false)}>Done</Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return <div className="flex min-h-12 items-center justify-between gap-4 border-b border-border/60 py-3 last:border-0"><span className="text-sm">{label}</span><span className="text-right text-sm text-muted-foreground">{value}</span></div>;
}

function ConnectedPlugs() {
  const { baseUrl } = useApiConfig();
  const { data: plugs, isError } = useSuspenseQuery(plugsQueryFor(baseUrl));
  if (isError || plugs === null) return <ApiBreakBox />;
  return <>
    {plugs.length === 0 && <p className="py-5 text-sm text-muted-foreground">No connected plugs</p>}
    {plugs.map(plug => <DeviceRow key={plug.id} plug={plug} />)}
  </>;
}

function DeviceRow({ plug }: { plug: Plug }) {
  const { baseUrl } = useApiConfig();
  const rename = useServerFn(renamePlug);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(plug.name ?? "");
  const qc = useQueryClient();
  const online = isPlugOnline(plug);
  const mutation = useMutation({
    mutationFn: () => baseUrl === DEFAULT_API_BASE_URL ? rename({ data: { id: plug.id, name } }) : renameApiPlug(baseUrl, plug.id, name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["plugs"] }); setOpen(false); },
  });
  return <>
    <Button variant="ghost" onClick={() => { setName(plug.name ?? ""); mutation.reset(); setOpen(true); }} className="h-auto min-h-16 w-full justify-between gap-3 whitespace-normal rounded-none border-b border-border/60 px-0 text-left font-normal">
      <span className="flex min-w-0 items-center gap-3"><Laptop className="!size-5 text-muted-foreground" /><span className="break-words">{plug.name ?? "Unnamed plug"}</span></span>
      <span className="flex shrink-0 items-center gap-2"><span className={`text-xs font-medium ${online ? "text-primary" : "text-destructive"}`}>{online ? "Online" : "Offline"}</span><ChevronRight className="text-muted-foreground" /></span>
    </Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-[calc(100%-3rem)] rounded-lg sm:max-w-sm">
        <DialogTitle>{plug.name ?? "Unnamed plug"}</DialogTitle>
        <DialogDescription>Connected plug · {online ? "Online" : "Offline"}</DialogDescription>
        <form onSubmit={e => { e.preventDefault(); if (name.trim()) mutation.mutate(); }} className="space-y-4">
          <label className="block text-sm font-medium" htmlFor={`plug-name-${plug.id}`}>Plug name</label>
          <Input id={`plug-name-${plug.id}`} value={name} onChange={e => setName(e.target.value)} maxLength={80} required />
          {mutation.isError && <p role="alert" className="text-sm text-destructive">{mutation.error.message}</p>}
          <Button type="submit" disabled={mutation.isPending || !name.trim()} className="w-full">{mutation.isPending ? "Saving…" : "Save"}</Button>
        </form>
      </DialogContent>
    </Dialog>
  </>;
}

// Example time-of-use prices (¢/kWh) for illustration — the API does not
// provide real rate data, so every chart is labelled as an example.
const HOURLY_PRICES = [
  12, 12, 12, 12, 12, 12, // 12am–5am off-peak
  18, 18, 22, 22, 22, 22, // 6am–11am mid
  22, 22, 22, 22, 34, 34, // 12pm–5pm, peak starts 4pm
  34, 34, 34, 22, 22, 12, // 6pm–11pm, peak ends 9pm
];
const PEAK_START = 16; // 4pm
const PEAK_END = 21; // 9pm
const isPeakHour = (hour: number) => hour >= PEAK_START && hour < PEAK_END;

function TouChart() {
  const max = Math.max(...HOURLY_PRICES);
  return (
    <figure className="mt-6" aria-label="Example electricity price for each hour of the day">
      <div className="flex h-28 items-end gap-[3px]" role="img" aria-label="Prices are lowest overnight, rise through the day, and peak between 4pm and 9pm">
        {HOURLY_PRICES.map((price, hour) => (
          <div
            key={hour}
            title={`${hour}:00 — ${price}¢/kWh`}
            className={`flex-1 rounded-sm ${isPeakHour(hour) ? "bg-destructive" : "bg-primary-foreground/45"}`}
            style={{ height: `${(price / max) * 100}%` }}
          />
        ))}
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-primary-foreground/70">
        <span>12am</span><span>6am</span><span>12pm</span><span>6pm</span><span>11pm</span>
      </div>
      <figcaption className="mt-3 flex items-center gap-4 text-xs text-primary-foreground/80">
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-primary-foreground/45" />Off-peak</span>
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-destructive" />Peak (4–9pm)</span>
      </figcaption>
    </figure>
  );
}

function PriceCompare() {
  const rows = [
    { label: "Off-peak", price: 12, note: "overnight & midday" },
    { label: "Mid-peak", price: 22, note: "morning & evening" },
    { label: "Peak", price: 34, note: "4pm – 9pm" },
  ];
  const max = Math.max(...rows.map(r => r.price));
  return (
    <figure className="mt-6 space-y-3" aria-label="Example price per kilowatt-hour by time of day">
      {rows.map(row => (
        <div key={row.label}>
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium">{row.label} <span className="text-primary-foreground/60">· {row.note}</span></span>
            <span className="font-semibold">{row.price}¢/kWh</span>
          </div>
          <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-primary-foreground/15">
            <div
              className={`h-full rounded-full ${row.label === "Peak" ? "bg-destructive" : "bg-primary-foreground/60"}`}
              style={{ width: `${(row.price / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </figure>
  );
}

function ShiftSave() {
  // Example: charging a laptop (60W) for 2 hours = 0.12 kWh.
  const kwh = 0.12;
  const peak = (kwh * 34) / 100;
  const offPeak = (kwh * 12) / 100;
  return (
    <figure className="mt-6" aria-label="Example cost of charging a laptop at peak versus off-peak times">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-destructive/90 px-4 py-4 text-center">
          <p className="text-xs font-medium text-primary-foreground/80">Charge at 6pm</p>
          <p className="mt-1 font-display text-2xl font-semibold">${peak.toFixed(2)}</p>
          <p className="mt-1 text-[10px] text-primary-foreground/70">peak price</p>
        </div>
        <div className="rounded-lg bg-primary-foreground/15 px-4 py-4 text-center">
          <p className="text-xs font-medium text-primary-foreground/80">Charge at 11pm</p>
          <p className="mt-1 font-display text-2xl font-semibold">${offPeak.toFixed(2)}</p>
          <p className="mt-1 text-[10px] text-primary-foreground/70">off-peak price</p>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs text-primary-foreground/80">
        Same charge, {Math.round((1 - offPeak / peak) * 100)}% less — just by waiting.
      </figcaption>
    </figure>
  );
}

const guide = [
  { title: "Your electricity rate plan", text: "Your provider sets what you pay for electricity. Many plans charge different prices at different times of day — here’s a typical example.", visual: <PriceCompare /> },
  { title: "Timing can make a difference.", text: "Prices often jump in the late afternoon and evening, when everyone is home using power. Your exact hours and prices depend on your provider and plan.", visual: <TouChart /> },
  { title: "A little shift can help.", text: "Moving flexible tasks — like charging your laptop — to cheaper hours can shrink your bill without changing how much you use.", visual: <ShiftSave /> },
];

function RateGuide({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [step, setStep] = useState(0);
  const slide = guide[step];
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-[calc(100%-2rem)] gap-6 rounded-lg border-primary bg-primary px-6 py-8 text-primary-foreground sm:max-w-sm [&>button]:text-primary-foreground">
      <div className="flex gap-1 pr-6" aria-label={`Part ${step + 1} of ${guide.length}`}>
        {guide.map((_, i) => <span key={i} className={`h-1 flex-1 rounded-full ${i <= step ? "bg-primary-foreground" : "bg-primary-foreground/30"}`} />)}
      </div>
      <p className="text-sm font-medium">Your rate plan · {step + 1}/{guide.length}</p>
      <div className="py-6">
        <DialogTitle className="font-display text-3xl leading-tight">{slide?.title}</DialogTitle>
        <DialogDescription className="mt-4 text-base leading-relaxed text-primary-foreground/90">{slide?.text}</DialogDescription>
        {slide?.visual}
        <p className="mt-3 text-[10px] text-primary-foreground/60">Example prices for illustration — connect your provider for your real rates.</p>
      </div>
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="icon" title="Previous part" aria-label="Previous part" disabled={step === 0} onClick={() => setStep(s => s - 1)} className="text-primary-foreground hover:bg-primary-foreground/15 hover:text-primary-foreground"><ArrowLeft /></Button>
        <Button variant="secondary" onClick={() => { if (step === guide.length - 1) { onOpenChange(false); setStep(0); } else setStep(s => s + 1); }}>{step === guide.length - 1 ? "Done" : "Next"}<ArrowRight /></Button>
      </div>
    </DialogContent>
  </Dialog>;
}