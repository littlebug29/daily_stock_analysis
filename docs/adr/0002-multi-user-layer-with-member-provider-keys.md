---
status: accepted
---

# Multi-user layer on a single-user upstream, billed through each Member's own Provider Key

Upstream is single-user (one admin password, the Owner's LLM keys, one watchlist). We add Members on top: invite-only, signing in with Telegram or Discord, each with their own Watchlist, Schedule, Portfolio and Provider Key, receiving deliveries by DM. Members pay for their own usage by bringing their own LLM key instead of paying the Owner, which keeps the deployment non-commercial and means the Owner never collects money. (When this was decided the market data source was vnstock, licensed for personal and non-commercial use only. vnstock was later replaced by provider adapters, with Yahoo Finance first; Yahoo's endpoint and the broker Open APIs considered next are likewise limited to personal use and forbid passing their data to third parties, so the non-commercial reasoning still holds and sharing reports with Members needs checking per provider.)

## Considered Options

- **Stay single-user like upstream**: rejected; friends need their own watchlists and portfolios.
- **Metered usage settled by bank transfer, or a paid subscription**: rejected; turns the project commercial and would require a licensed data source.
- **One shared Decision Report per Instrument**: rejected once billing moved to Provider Keys; there is no fair payer for a shared report, and each Member should get the model they pay for.

## Consequences

Decision Reports and Market Review commentary are produced per Member, so an Instrument watched by three Members is analysed three times; only the Market Snapshot is shared. A Member whose Provider Key is missing, invalid or out of quota receives only an alert for that run. Upstream's API, scheduler and storage code must become Member-aware, which is the largest source of divergence from upstream.
