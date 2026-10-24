import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { Lightbulb, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getSavingsRecommendation, type RecommendationResult } from "@/lib/recommendation.functions";

export const Route = createFileRoute("/recommend")({
  head: () => ({ meta: [
    { title: "Judy — Savings tips" },
    { name: "description", content: "Tell Judy about a socket alert and your recent usage to get a personalized way to cut peak-hour energy costs." },
    { property: "og:title", content: "Judy — Savings tips" },
    { property: "og:description", content: "A personalized tip to cut peak-hour energy costs, based on your socket alert and usage." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: Recommend,
});

function Recommend() {
  const [alert, setAlert] = useState("");
  const [usage, setUsage] = useState("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<RecommendationResult | null>(null);
  const ask = useServerFn(getSavingsRecommendation);

  const canSubmit = alert.trim().length > 0 && usage.trim().length > 0 && !pending;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setPending(true);
    setResult(null);
    try {
      const res = await ask({ data: { alert: alert.trim(), usage: usage.trim() } });
      setResult(res);
    } catch (error) {
      setResult({
        ok: false,
        error: error instanceof Error ? error.message : "Something went wrong — please try again.",
        retryable: true,
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto min-h-dvh max-w-md px-6 pb-28 pt-8">
      <header className="flex items-center justify-between">
        <h1 className="font-display text-5xl font-semibold text-primary">Judy</h1>
        <span className="rounded-full bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">Savings</span>
      </header>
      <main className="mt-8">
        <h2 className="font-display text-2xl font-semibold">Cut your peak-hour costs</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Tell Judy about a socket alert and your recent usage, and get a personalized tip for your 4–9pm peak window.
        </p>

        <form onSubmit={onSubmit} className="mt-5 space-y-4 rounded-lg bg-card px-4 py-4 shadow-[var(--shadow-card)]">
          <div className="space-y-1.5">
            <Label htmlFor="alert">Socket alert</Label>
            <Textarea
              id="alert"
              value={alert}
              onChange={(e) => setAlert(e.target.value)}
              placeholder="e.g. Laptop has been charging since 3pm and is still drawing power"
              maxLength={500}
              rows={3}
              className="resize-none"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="usage">Recent usage</Label>
            <Textarea
              id="usage"
              value={usage}
              onChange={(e) => setUsage(e.target.value)}
              placeholder="e.g. I usually charge it 4–7pm on weekdays, about 2 hours a day"
              maxLength={1000}
              rows={3}
              className="resize-none"
            />
          </div>
          <Button type="submit" disabled={!canSubmit} className="h-11 w-full rounded-full">
            {pending ? (
              <><Loader2 className="!size-4 animate-spin" />Thinking…</>
            ) : (
              <><Sparkles className="!size-4" />Get my tip</>
            )}
          </Button>
        </form>

        {result?.ok && (
          <section aria-label="Your personalized tip" className="mt-5 rounded-lg bg-primary/10 px-4 py-4">
            <div className="flex items-center gap-2 text-primary">
              <Lightbulb className="!size-5" />
              <h3 className="font-display text-lg font-semibold">Your tip</h3>
            </div>
            <p className="mt-2 text-sm leading-relaxed">{result.recommendation}</p>
          </section>
        )}

        {result && !result.ok && (
          <section aria-label="Could not get a tip" className="mt-5 rounded-lg bg-destructive/10 px-4 py-4">
            <p className="text-sm text-destructive">{result.error}</p>
          </section>
        )}
      </main>
    </div>
  );
}
