"use client";
import { InsightPreferences } from "./insight-preferences";
import { useState } from "react";
import FundamentalAnalysis from "./fundamental-analysis";
import CrossFundamentalAnalysis from "./cross-fundamental-analysis";
import { Button } from "./ui";
export default function ResearchFundamentals() {
  const [market, setMarket] = useState("equity");
  return (
    <InsightPreferences>
      <div className="space-y-5">
        <nav aria-label="Fundamental markets" className="flex flex-wrap gap-3">
          {[
            ["equity", "Stocks · SEC"],
            ["EURUSD", "EURUSD · Macro"],
            ["BTCUSD", "BTCUSD · Network"],
          ].map(([id, label]) => (
            <Button
              key={id}
              variant={market === id ? "primary" : "secondary"}
              aria-pressed={market === id}
              onClick={() => setMarket(id)}
            >
              {label}
            </Button>
          ))}
        </nav>
        {market === "equity" ? (
          <FundamentalAnalysis />
        ) : (
          <CrossFundamentalAnalysis key={market} symbol={market as "EURUSD" | "BTCUSD"} />
        )}
      </div>
    </InsightPreferences>
  );
}
