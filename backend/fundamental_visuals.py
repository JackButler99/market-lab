"""Chart specifications derived only from the currently pinned fundamental snapshot."""

import datetime as dt
import math


def value(v):
    return (
        float(v)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        else None
    )


def day(v):
    try:
        return dt.date.fromisoformat(v)
    except (ValueError, TypeError):
        return None


def series(key, label, points):
    return {"id": key, "label": label, "points": sorted(points, key=lambda p: p["date"])}


def spec(card, title, unit, series_list, kind="line", frequency="daily", note=""):
    return {
        "card_id": card,
        "title": title,
        "unit": unit,
        "kind": kind,
        "frequency": frequency,
        "series": series_list,
        "max_gap_days": 45 if frequency == "monthly" else 4,
        "note": note,
        "zero_baseline": kind == "bar",
    }


def equity(analysis, period, today):
    years = sorted(
        [
            y
            for y in analysis.get("years", [])
            if day(y.get("end")) and y["end"] <= period and day(y["end"]) <= today
        ],
        key=lambda y: y["end"],
    )

    def val(y, key):
        return value(y.get("metrics", {}).get(key, {}).get("value"))

    def points(key, calculate=None):
        return [
            {"date": y["end"], "value": calculate(y) if calculate else val(y, key)} for y in years
        ]

    def margin(y):
        ni, r = val(y, "net_income"), val(y, "revenue")
        return ni / r * 100 if ni is not None and r is not None and r > 0 else None

    def fcf(y):
        cfo, capex = val(y, "operating_cash_flow"), val(y, "capex")
        return cfo - capex if cfo is not None and capex is not None and capex >= 0 else None

    def chart(card, title, unit, items):
        return spec(
            card,
            title,
            unit,
            items,
            "bar",
            "annual",
            "Periode tahunan dari filing yang sama; periode setelah pilihanmu tidak disertakan. Batang dimulai dari nol; nilai negatif tetap ditampilkan.",
        )

    return [
        chart(
            "revenue",
            "Pendapatan per periode tahunan",
            "USD",
            [series("revenue", "Pendapatan", points("revenue"))],
        ),
        chart(
            "net_margin",
            "Bagian pendapatan yang menjadi laba bersih",
            "%",
            [series("net_margin", "Net margin", points("net_margin", margin))],
        ),
        chart(
            "cash_conversion",
            "Bandingkan laba dengan kas operasi",
            "USD",
            [
                series(k, l, points(k))
                for k, l in [("net_income", "Laba bersih"), ("operating_cash_flow", "Kas operasi")]
            ],
        ),
        chart(
            "free_cash_flow",
            "Kas operasi, belanja aset tetap dan sisanya",
            "USD",
            [
                series("operating_cash_flow", "Kas operasi", points("operating_cash_flow")),
                series("capex", "Capex", points("capex")),
                series("free_cash_flow", "FCF (turunan)", points("free_cash_flow", fcf)),
            ],
        ),
        chart(
            "liabilities_assets",
            "Aset dan kewajiban yang dilaporkan",
            "USD",
            [
                series(k, l, points(k))
                for k, l in [("assets", "Aset"), ("liabilities", "Liabilitas")]
            ],
        ),
    ]


def cross(analysis, symbol, today):
    metrics = analysis.get("metrics", {})

    def history(key):
        return [
            {"date": p["date"], "value": value(p.get("value"))}
            for p in metrics.get(key, {}).get("history", [])
            if day(p.get("date"))
            and day(p["date"]) <= today
            and (symbol != "BTCUSD" or day(p["date"]) < today)
        ]

    def yoy(key):
        rows = history(key)
        lookup = {p["date"]: p["value"] for p in rows}
        result = []
        for p in rows:
            current = day(p["date"])
            if current.day != 1:
                continue
            old = lookup.get(current.replace(year=current.year - 1).isoformat())
            val = (
                (p["value"] / old - 1) * 100
                if p["value"] is not None and old is not None and old > 0
                else None
            )
            # Keep missing points to make missing comparison months explicit.
            result.append({"date": p["date"], "value": val})
        return result

    if symbol == "BTCUSD":
        result = []
        for key in ("hash-rate", "difficulty", "n-transactions", "total-bitcoins"):
            metric = metrics.get(key, {})
            item = spec(
                key,
                metric.get("label", key),
                metric.get("unit", ""),
                [series(key, metric.get("label", key), history(key))],
                "step" if key == "difficulty" else "line",
                note="Sampel provider per hari UTC selesai; celah lebih dari satu hari tidak dihubungkan. Rentang mengikuti observasi terakhir, bukan tanggal unduhan.",
            )
            item["max_gap_days"] = 1
            if key == "total-bitcoins":
                item[
                    "note"
                ] += " Suplai memakai timestamp terakhir yang tersedia per hari, bukan penjumlahan atau midnight close yang dijamin."
            result.append(item)
        return result
    us, ea = history("us_rate"), history("ea_rate")
    common = {p["date"] for p in us if p["value"] is not None} & {
        p["date"] for p in ea if p["value"] is not None
    }
    rate_note = "Rate efektif AS dan rate deposito ECB memiliki konsep berbeda. Grafik perbandingan hanya memakai tanggal yang sama; bukan sinyal arah kurs."
    return [
        spec(
            "us_rate",
            "Bunga efektif AS · observasi harian",
            "%",
            [series("us_rate", "US effective rate", us)],
        ),
        spec(
            "ea_rate",
            "Bunga deposito ECB · observasi harian",
            "%",
            [series("ea_rate", "ECB deposit rate", ea)],
            "step",
        ),
        spec(
            "rate_spread",
            "Dua rate pada tanggal yang sama",
            "%",
            [
                series("us_rate", "US effective rate", [p for p in us if p["date"] in common]),
                series("ea_rate", "ECB deposit rate", [p for p in ea if p["date"] in common]),
            ],
            note=rate_note,
        ),
        spec(
            "us_inflation",
            "Perubahan tahunan CPI AS",
            "%",
            [series("us_inflation", "US CPI YoY", yoy("us_cpi"))],
            frequency="monthly",
            note="YoY dari indeks NSA dengan bulan pembanding tepat satu tahun lalu. Bulan yang tidak dapat dihitung tetap kosong.",
        ),
        spec(
            "ea_inflation",
            "Perubahan tahunan HICP zona euro",
            "%",
            [series("ea_inflation", "EA HICP YoY", yoy("ea_hicp"))],
            frequency="monthly",
            note="YoY dari indeks NSA; keranjang HICP berbeda dari CPI AS. Celah bulan tidak diisi/interpolasi.",
        ),
    ]


def build(analysis, symbol, period, today):
    return (
        equity(analysis, period, today)
        if symbol in ("AAPL", "MSFT")
        else cross(analysis, symbol, today)
    )
