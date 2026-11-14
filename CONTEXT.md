# Vietnam Daily Stock Analysis

A fork of daily_stock_analysis restricted to the Vietnamese market and Vietnamese news, with a multi-user layer on top: each invited Member gets scheduled Market Reviews and Decision Reports for their own Watchlist, made with their own LLM key and delivered by direct message, plus the web workbench, Assistant, Portfolio, and Backtests. An Owner-only Mode keeps the upstream single-user deployments working.

## Language

### Market

**Exchange**:
One of the three Vietnamese venues in scope: HOSE, HNX, UPCoM.
_Avoid_: Sàn (in code/docs), market, bourse

**Instrument**:
A tradable security listed on an Exchange that the tool can analyse; in scope are common stocks and ETFs only.
_Avoid_: Ticker, symbol, mã (a ticker is the instrument's code, not the instrument)

**Index**:
A Vietnamese market index (VN-Index, VN30, HNX-Index, UPCoM-Index, and similar) that can be analysed like an Instrument but not traded.
_Avoid_: Benchmark, chỉ số (in code)

**Sector**:
An ICB industry group, optionally extended by a small curated set of Vietnamese themes, used to rank and compare Instruments.
_Avoid_: Concept board, industry, ngành (in code)

**Trading Day**:
A calendar day on which the Vietnamese exchanges hold a regular session; weekends and Vietnamese public holidays (including Tết) are not Trading Days.
_Avoid_: Business day, session day

**Market Phase**:
A part of a Trading Day: pre-open, ATO, morning continuous, lunch break, afternoon continuous, ATC, post-close; or non-trading.
_Avoid_: Session (ambiguous), period

**Reference Price**:
The price an Instrument's Price Band is computed from for a Trading Day, normally the previous Trading Day's close.
_Avoid_: Giá tham chiếu (in code), base price, previous close

**Price Band**:
The range an Instrument may trade within on a Trading Day, bounded by the Ceiling Price and Floor Price; its width depends on the Exchange (±7% HOSE, ±10% HNX, ±15% UPCoM).
_Avoid_: Limit, daily limit, biên độ (in code)

**Ceiling Price** / **Floor Price**:
The upper and lower bounds of the Price Band.
_Avoid_: Limit-up / limit-down, giá trần / giá sàn (in code)

**Tick Size**:
The smallest price increment allowed for an Instrument, set by its Exchange and price level.
_Avoid_: Step, bước giá (in code)

**Settlement Lag**:
The waiting period (currently T+2, about 2.5 Trading Days) after buying before shares can be sold.
_Avoid_: T+ (as a bare term), lock-up

**Foreign Flow**:
Net buy minus sell value by foreign investors in an Instrument or the whole market for a Trading Day.
_Avoid_: Khối ngoại (in code), foreign trading, main-force money

**Foreign Room**:
How much more of an Instrument foreign investors may still own before reaching the legal foreign ownership limit.
_Avoid_: Room ngoại (in code), FOL headroom

**Proprietary Flow**:
Net buy minus sell value by securities firms trading their own account.
_Avoid_: Tự doanh (in code), prop trading, main-force money

**Traded Value**:
Total value of matched trades in an Instrument or market for a Trading Day; the main liquidity measure.
_Avoid_: GTGD (in code), turnover, volume (volume is share count, not value)

**Put-through Trade**:
A negotiated block trade reported outside the order-matching book.
_Avoid_: Thỏa thuận (in code), block deal, dragon-tiger

**Insider Trade**:
A disclosed trade by an insider, major shareholder or related party of the issuing company.
_Avoid_: Giao dịch nội bộ (in code), director dealing

**Market Snapshot**:
The market data for a Trading Day at a Market Phase (prices, indices, breadth, flows, Sectors), fetched once and shared by every Member's analysis.
_Avoid_: Market data dump, cache

### People and modes

**Owner**:
The person who runs the deployment and approves who may become a Member.
_Avoid_: Admin, operator

**Member**:
An approved person who signs in with Telegram or Discord and has their own Watchlist, Portfolio, Provider Key and Schedule.
_Avoid_: User, account, customer, subscriber

**Provider Key**:
A Member's own LLM API key; every LLM cost for that Member (reports, review commentary, chat, imports) is billed to it.
_Avoid_: Token, credentials, API key (unqualified)

**Owner-only Mode**:
The upstream-style single-user deployment (GitHub Actions, Desktop, local) configured from environment settings, with no Members.
_Avoid_: Legacy mode, single mode, lite

### Analysis

**Watchlist**:
The set of Instruments and Indices a Member wants analysed; each Member has exactly one.
_Avoid_: Portfolio (a portfolio implies holdings), stock list

**Schedule**:
The time slots at which a Member's Analysis Runs happen; the default is the single post-close slot, and extra slots come from an Owner-approved list.
_Avoid_: Cron, timer

**Analysis Run**:
One scheduled analysis at a given Market Phase that builds or reuses the Market Snapshot, then produces each due Member's Market Review and Decision Reports.
_Avoid_: Job, batch, daily run

**Post-close Run**:
The Analysis Run in the post-close phase, when end-of-day data is final; every Member gets it by default.
_Avoid_: Daily run, EOD job

**Decision Report**:
One Member's analysis of one Instrument at one Analysis Run, made with that Member's Provider Key: conclusion, Signal, score, trend, Trade Plan, risks, catalysts, and checklist.
_Avoid_: Dashboard, analysis, recommendation

**Signal**:
The Decision Report's headline verdict, one of Mua (Buy), Theo dõi (Watch), Bán (Sell).
_Avoid_: Rating, recommendation, action

**Trade Plan**:
The buy zone, stop-loss and target prices in a Decision Report, rounded to Tick Size, inside the Price Band, and consistent with the Settlement Lag.
_Avoid_: Price levels, buy/sell points

**Market Review**:
A Member's market-wide summary for an Analysis Run: Market Snapshot figures plus LLM commentary written with that Member's Provider Key, delivered before their Decision Reports.
_Avoid_: Market recap, overview, tổng quan

### Portfolio

**Portfolio**:
A Member's holdings, derived from their Trade Log; shown in the web UI only, never in deliveries or Decision Reports.
_Avoid_: Positions, account, holdings (as the stored thing)

**Trade Log**:
The ordered record of a Member's Trades and Corporate Actions, from which Portfolio quantities, cost basis and P&L are derived.
_Avoid_: Transaction history, orders

**Trade**:
One executed buy or sell of an Instrument by a Member, with date, quantity, price, broker fee and (for sells) sell tax.
_Avoid_: Order (an order may not be filled), transaction

**Corporate Action**:
A dividend, stock dividend, rights issue or split that changes a Member's quantity or cost basis without a Trade.
_Avoid_: Event, adjustment

**Broker Connection**:
A Member's opt-in, read-only link to their DNSE or SSI account that fills their Trade Log from the broker; it never places orders.
_Avoid_: Broker sync, integration, trading account

**Import**:
Turning an external file into Watchlist entries (CSV/Excel, screenshot, clipboard) or Trades (SSI, VPS, TCBS statements).
_Avoid_: Upload, sync

### Strategy and evaluation

**Strategy**:
A named set of rules or analysis approach defined in YAML (upstream strategies plus Vietnam-specific ones); used by both the Assistant and Backtests.
_Avoid_: Model, system, setup

**Backtest**:
A rule-based simulation of a Strategy over historical Market Snapshots, honouring fees, sell tax, Tick Size, Price Band and Settlement Lag; no LLM involved.
_Avoid_: Simulation, test run

**Track Record**:
The measured outcome of past Decision Reports: forward returns after each Signal and whether the Trade Plan's target or stop-loss was hit first.
_Avoid_: Backtest (a backtest replays rules; a track record scores real past Signals), performance

### Delivery and chat

**Channel**:
A messaging platform reports are delivered to; Members use Telegram or Discord direct messages, and Owner-only Mode may also use Slack, email, ntfy, Gotify, Pushover or a webhook.
_Avoid_: Notifier, sink, platform

**Assistant**:
The chat agent a Member talks to in the web UI or by Channel DM; it can read market data, Decision Reports, Strategies and the Member's own data, and can edit that Member's Watchlist and Trade Log.
_Avoid_: Bot (the bot is the Channel integration), agent, AI
