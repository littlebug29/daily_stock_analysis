# Vietnam market

This fork analyses Vietnamese Instruments only (see `CONTEXT.md` and `docs/adr/`). This page covers what is available today.

**Current phase: HOSE only.** Stocks and ETFs listed on HOSE, and VN-Index, can be analysed. HNX and UPCoM Instruments and indices are rejected with a "giai đoạn này chỉ hỗ trợ HOSE" reason; they come in later phases (the gate is `SUPPORTED_EXCHANGES` in `src/vn/instruments.py`). It is English-only: the fork targets Vietnamese users, and reports themselves are Vietnamese (`REPORT_LANGUAGE=vi`).

## Codes

| Kind | Examples | Supported |
| --- | --- | --- |
| Common stock (3 characters) on HOSE | `FPT`, `VNM`, `HPG` | Yes |
| ETF on HOSE | `E1VFVN30`, `FUEVFVND`, `FUESSV30` | Yes |
| HOSE index | `VNINDEX` | Yes (`VN30`, `VN100`: recognised, but Yahoo has no data for them) |
| HNX / UPCoM stock, ETF or index | `SHS`, `PVS`, `VEA`, `HNXINDEX`, `UPCOMINDEX` | Not in this phase, rejected with a reason |
| Covered warrant | `CFPT2501` | No, rejected with a reason |
| Futures | `VN30F2412`, `VN30F1M` | No, rejected with a reason |

A `.VN` suffix is accepted and stripped. Vietnamese code shapes take precedence over other markets' code shapes, so any 3-character code is read as a Vietnamese Instrument (for example `IBM` is looked up on the Vietnamese exchanges). Codes of other markets are still routed to their upstream data sources until those markets are removed.

## Market data providers

Vietnamese data comes through provider adapters listed in `VN_DATA_PROVIDERS`, in priority order (default `yfinance`). Each request tries the providers in turn and falls back to the next one when a provider fails or has no data for the code.

| Provider | Name in `VN_DATA_PROVIDERS` | Covers | Access |
| --- | --- | --- | --- |
| Yahoo Finance | `yfinance` | HOSE stocks and ETFs (`FPT.VN`), VN-Index (`^VNINDEX.VN`) | Free, no key. Unofficial endpoint, personal use. |

Not covered yet by any provider: VN30/VN100 index levels, Ceiling/Floor Prices, Foreign/Proprietary Flow (and HNX/UPCoM, which are out of this phase). Codes no provider covers fail with the reason from each provider (for example `yfinance: SHS: no data from Yahoo Finance (SHS.VN)`). Yahoo returns no data both for codes it doesn't carry and when it is unreachable or rate-limiting, so the message names both.

Adding a provider (e.g. a broker Open API such as TCBS, SSI or DNSE): implement the `VnMarketDataProvider` protocol in `data_provider/vn_market/` (daily bars and latest session, returned in thousand đồng), register its class in `PROVIDERS` in `data_provider/vn_market/fetcher.py`, and add its name to `VN_DATA_PROVIDERS`.

Prices are kept in **thousand đồng**, what price boards show: `120.5` means 120,500 đ. Index levels stay in points.

With Yahoo the Exchange comes from Yahoo's listing metadata (Yahoo only lists HOSE, so it defaults to HOSE when the name doesn't parse), the next-session Reference Price is the latest close, and Traded Value is not available. A provider that raises or returns nothing passes to the next provider. If `VN_DATA_PROVIDERS` names no known provider, Vietnamese codes fail with a message to fix it.

## Trading calendar

`src/vn/data/holidays.json` lists the weekday closures announced by HOSE/HNX. Only 2026 is listed. **Update it every year** when the exchanges publish the calendar (Tết moves every year). A year missing from the file falls back to weekday-only checks and logs a warning. `--force-run` skips the Trading Day check as usual.

## Decision Reports in Vietnamese

Set `REPORT_LANGUAGE=vi`. Signals use three words: **Mua**, **Theo dõi**, **Bán**. Upstream's finer actions map onto them: buy/add → Mua; hold/watch/avoid/alert → Theo dõi; reduce/sell → Bán.

After the LLM writes the Trade Plan, every price in it is rounded to the Exchange Tick Size (HOSE: 0.01 below 10, 0.05 from 10 to below 50, 0.1 from 50; HNX/UPCoM: 0.1; ETFs: 0.01 on HOSE, 0.001 on HNX). Then:

- **Buy zones** are orders for the next session, so they are kept inside its Price Band (±7% HOSE, ±10% HNX, ±15% UPCoM).
- **Stop-loss and target** can be reached over several sessions, so they are not moved; when they lie outside the next Price Band the report says so.
- The report shows the next-session Reference Price, Floor and Ceiling, and notes that shares bought today can only be sold after T+2.
- Numbers that aren't prices are left alone: indicator periods (`MA 10`), dates (`13/11`), percentages and counts of time (`120 phiên`, `100 ngày`).
- When the rules can't be applied (Exchange or Reference Price unknown), the report says so under the Trade Plan instead of silently leaving prices unadjusted.

The next-session Reference Price is today's close on HOSE and HNX, and today's volume-weighted average price on UPCoM (needs a provider that reports Traded Value; otherwise the close is used). It is exact for Post-close Runs; intraday runs use the latest available data.

## Not yet available

Foreign/Proprietary Flow, Vietnamese news, the Vietnam Market Review, intraday Market Phases, and rejecting other markets' codes are tracked as separate tickets on the fork.
