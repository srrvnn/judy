export function ApiBreakBox() {
  return (
    <div role="status" className="rounded-lg bg-unavailable px-6 py-8 text-unavailable-foreground">
      <p className="font-display text-2xl font-semibold leading-snug">taking a break, we will be right back :)</p>
    </div>
  );
}

export function ApiBreakScreen() {
  return (
    <div className="mx-auto min-h-dvh max-w-md px-6 pb-28 pt-8">
      <header><h1 className="font-display text-5xl font-semibold text-primary">Judy</h1></header>
      <main className="mt-6"><ApiBreakBox /></main>
    </div>
  );
}
