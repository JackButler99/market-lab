"use client";
import { PUBLIC_READ_ONLY } from "./api-base";
import { Button, Panel, Pill } from "./ui";
import AutomationStatus from "./automation-status";
export type DatasetAsset = {
  symbol: string;
  source: string;
  as_of: string;
  observations: number;
  dataset_id: string;
  start_date: string;
  price_basis: string;
  frequency: string;
  calendar: string;
  provider: string;
  date_policy?: string;
  missing_weekdays?: string[];
  fetched_at: string | null;
  last_sync: { status: string; started: string; finished: string | null; message: string } | null;
};
export default function MarketSync({
  asset,
  busy,
  onSync,
}: {
  asset: DatasetAsset | undefined;
  busy: boolean;
  onSync: () => void;
}) {
  if (!asset) return null;
  if (typeof asset.dataset_id !== "string" || !asset.dataset_id.trim()) {
    return (
      <Panel className="mb-5" role="alert">
        <h2 className="text-base font-medium text-[#f0b47a]">Backend update required</h2>
        <p className="mt-2 text-xs leading-6 text-muted">
          The API returned prices without dataset metadata. Stop the old Python server, then start
          the updated backend from this project and refresh the page.
        </p>
      </Panel>
    );
  }
  const supported = ["AAPL", "MSFT", "EURUSD", "BTCUSD"].includes(asset.symbol);
  return (
    <Panel className="mb-5" data-tour="market-sync">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-medium">
            Daily market data <span className="text-muted">/ {asset.symbol}</span>
          </h2>
          <p className="mt-2 text-xs leading-6 text-muted">
            {supported
              ? "Sync daily prices from Alpha Vantage. API key belongs in backend/.env."
              : "API connector is available for AAPL, MSFT, EURUSD and BTCUSD. CSV import remains available for this asset."}
          </p>
        </div>
        <Button
          variant="primary"
          disabled={PUBLIC_READ_ONLY || busy || !supported}
          onClick={onSync}
        >
          {busy ? "Processing…" : "↻ Sync market data"}
        </Button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Pill>{asset.source}</Pill>
        <Pill>{asset.price_basis}</Pill>
        <Pill>{asset.calendar}</Pill>
        <Pill>{asset.frequency}</Pill>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-4 text-xs max-[650px]:grid-cols-1">
        <div>
          <dt className="text-muted">Dataset version</dt>
          <dd className="mt-1 break-all font-mono text-accent" title={asset.dataset_id}>
            {asset.dataset_id.slice(0, 16)}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Stored range</dt>
          <dd className="mt-1">
            {asset.start_date} → {asset.as_of} · {asset.observations} rows
          </dd>
        </div>
      </dl>
      {asset.fetched_at && (
        <p className="mt-3 text-xs text-muted">
          Last successful fetch: {new Date(asset.fetched_at).toLocaleString()}
        </p>
      )}
      {asset.last_sync && (
        <div
          role="status"
          className="mt-4 rounded-md border border-line bg-canvas p-3 text-xs leading-6"
        >
          <span
            className={asset.last_sync.status === "succeeded" ? "text-accent" : "text-[#f0b47a]"}
          >
            {asset.last_sync.status.toUpperCase()}
          </span>{" "}
          · {new Date(asset.last_sync.finished || asset.last_sync.started).toLocaleString()}
          <p className="text-muted">{asset.last_sync.message}</p>
        </div>
      )}
      {asset.symbol === "EURUSD" && (
        <div className="mt-4 rounded-md border border-line bg-canvas p-3 text-xs leading-6 text-muted">
          <p>
            EUR/USD quote: USD per EUR. API data uses completed UTC dates and a weekday-only grid,
            not XNYS or New York 5pm sessions. Current-date and weekend bars are excluded.
          </p>
          {asset.missing_weekdays && asset.missing_weekdays.length > 0 && (
            <p className="mt-2 text-[#f0b47a]">
              {asset.missing_weekdays.length} weekday dates are absent from the provider history.
              Values are not forward-filled; forecast weekdays may include holidays without quotes.
            </p>
          )}
        </div>
      )}
      {asset.symbol === "BTCUSD" && (
        <div className="mt-4 rounded-md border border-line bg-canvas p-3 text-xs leading-6 text-muted">
          BTC/USD uses completed UTC daily bars, including Saturdays and Sundays. The current UTC
          date is excluded. This is a provider daily reference series, not an executable price from
          a selected exchange, and it is not BTC/USDT.
        </div>
      )}
      <AutomationStatus symbol={asset.symbol} />
      <p className="mt-4 text-[11px] leading-6 text-muted">
        Daily data with backend auto-sync and a manual override, not a streaming feed. First API
        sync replaces synthetic/CSV prices for this asset; later syncs merge API observations.
        {asset.symbol === "EURUSD"
          ? "FX compact requests fetch 100 raw daily rows; fewer remain after filtering."
          : asset.symbol === "BTCUSD"
            ? "Crypto uses DIGITAL_CURRENCY_DAILY history; this endpoint has no compact outputsize option."
            : "Equity prices are unadjusted and do not account for stock splits or dividends. Compact requests fetch 100 rows."}{" "}
        Provider quotas apply.
      </p>
    </Panel>
  );
}
