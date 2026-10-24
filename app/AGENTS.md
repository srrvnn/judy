<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

<!-- AGENT:BEGIN -->
> [!IMPORTANT]
> The dashboard's attention state (which device counts as online, and whether the
> screen reads all-is-well or needs-attention) lives only in `src/lib/status.ts`,
> covered by `src/test/plug-status.test.ts`. Routes and components must read that
> helper instead of re-deriving online/offline inline, so the colour rule stays a
> single tested decision.
<!-- AGENT:END -->

- Home and Profile share `src/lib/plugs-query.ts` and the root-mounted bottom navigation, so both views use one live device cache and consistent navigation.
- Home and Profile use a shared API-unavailable display and query-backed error recovery, so initial failures and refresh failures stay consistent and recover automatically.
- A root-mounted NotificationsProvider owns a single browser EventSource connection to the CORS-enabled upstream, preserving notifications across page navigation without a proxy or local persistence; `src/lib/events.ts` validates and deduplicates replayed messages.
- Notification streams keep one visit-start timestamp per endpoint and filter earlier event creation times through the tested events helper, so refresh clears history without dropping new alerts or reintroducing history on reconnect.
- Keep AI SDK adapters and core on a shared provider contract via the package override to avoid incompatible duplicate model types.
- Dismissal uses provider-owned session-only event IDs and shared event filtering so dismissed alerts cannot reappear on SSE replay, while newly arriving alerts still appear.
- The notification provider retains per-device acknowledgement context separately from active alerts; the shared status helper decides acknowledgement versus attention, so navigation preserves decisions and new critical events take precedence.
- Home's colour preview is visit-only UI state applied through the status helper; preview events have no server action IDs, so previewing cannot operate a physical device.
- Notification severity comes from the API severity field (legacy kind fallback); resolved messages do not flag devices. Home actions POST only server-supplied action IDs to the CORS-enabled upstream, preserving errors and accepting resolution only after API confirmation.
- A root API configuration provider stores only the endpoint preference in this browser; endpoint-keyed queries and the notification stream switch together and isolate data from different servers. Custom URLs use browser requests (requiring upstream CORS) rather than a user-controlled server proxy to avoid SSRF; the fixed default retains its existing server proxy.
