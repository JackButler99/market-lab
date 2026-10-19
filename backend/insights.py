"""Deterministic, snapshot-bound fundamental education. Never calls a provider or LLM."""

import datetime as dt
import math

import fundamental_visuals

VERSION = "fundamental-insight-v2"
SUPPORTED = {"AAPL", "MSFT", "EURUSD", "BTCUSD"}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def fmt(value, unit=""):
    if value is None:
        return "tidak tersedia"
    return f"{value:,.2f}" + (" " + unit if unit else "")


def date(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def card(
    key,
    title,
    value,
    unit,
    fact,
    beginner,
    intermediate,
    expert,
    caveat,
    next_steps,
    evidence,
    formula=None,
    comparison=None,
):
    return {
        "id": key,
        "title": title,
        "value": value,
        "unit": unit,
        "fact": fact,
        "readings": {"beginner": beginner, "intermediate": intermediate, "expert": expert},
        "caveat": caveat,
        "next_steps": next_steps,
        "evidence": evidence,
        "formula": formula,
        "comparison": comparison,
    }


def equity(analysis, selected, today):
    years = sorted(analysis.get("years", []), key=lambda y: y["end"], reverse=True)
    year = (
        next((y for y in years if y["end"] == selected), None)
        if selected
        else next(iter(years), None)
    )
    if not year:
        raise ValueError("Annual period not found in the saved fundamental snapshot")
    idx = years.index(year)
    previous = years[idx + 1] if idx + 1 < len(years) else None
    contiguous = bool(
        previous
        and date(year["start"])
        and date(previous["end"])
        and (date(year["start"]) - date(previous["end"])).days == 1
    )

    def val(key, y=year):
        return number(y.get("metrics", {}).get(key, {}).get("value")) if y else None

    def evidence(keys, include_previous=False):
        result = []
        for y in ([year, previous] if include_previous and contiguous else [year]):
            if not y:
                continue
            for key in keys:
                metric = y.get("metrics", {}).get(key, {})
                ev = metric.get("evidence")
                if val(key, y) is not None and ev:
                    result.append({"metric": key, "source": "SEC EDGAR", "period": y["end"], **ev})
        return result

    revenue, income, cfo, capex = (
        val(k) for k in ("revenue", "net_income", "operating_cash_flow", "capex")
    )
    old_revenue = val("revenue", previous)
    growth = (
        (revenue / old_revenue - 1) * 100
        if contiguous and revenue is not None and old_revenue is not None and old_revenue > 0
        else None
    )
    margin = (
        income / revenue * 100
        if income is not None and revenue is not None and revenue > 0
        else None
    )
    old_income = val("net_income", previous)
    old_margin = (
        old_income / old_revenue * 100
        if contiguous and old_income is not None and old_revenue is not None and old_revenue > 0
        else None
    )
    margin_change = margin - old_margin if margin is not None and old_margin is not None else None
    free = cfo - capex if cfo is not None and capex is not None and capex >= 0 else None
    conversion = cfo / income if cfo is not None and income is not None and income > 0 else None
    cards = [
        card(
            "revenue",
            "Skala dan pertumbuhan bisnis",
            revenue,
            "USD",
            f"Pendapatan periode {year['start']}–{year['end']}: {fmt(revenue, 'USD')}. Pertumbuhan tahunan: {fmt(growth, '%')}.",
            "Pendapatan adalah nilai penjualan yang diakui perusahaan. Perubahan pendapatan membantu melihat apakah skala penjualan bertambah atau berkurang.",
            "Pertumbuhan perlu dibaca bersama margin dan arus kas. Perubahan dapat melibatkan volume, harga, akuisisi atau kurs; penyebabnya belum diketahui dari angka ini.",
            "YoY hanya dihitung jika periode tahunan berurutan dan pendapatan pembanding positif. Periksa pengakuan pendapatan, perubahan segmen dan restatement pada catatan filing.",
            "Pendapatan naik tidak otomatis berarti laba atau harga saham naik.",
            [
                "Bandingkan margin dan arus kas operasi.",
                "Baca MD&A untuk memeriksa penjelasan manajemen; teksnya belum diekstrak aplikasi.",
            ],
            evidence(["revenue"], True),
            "(revenue / prior contiguous annual revenue - 1) × 100",
            {"value": growth, "unit": "%", "prior_period": previous["end"] if contiguous else None},
        ),
        card(
            "net_margin",
            "Laba yang tersisa dari penjualan",
            margin,
            "%",
            f"Margin laba bersih: {fmt(margin, '%')}; perubahan tahunan: {fmt(margin_change, 'poin persentase')}.",
            "Margin menunjukkan berapa bagian pendapatan yang menjadi laba bersih. Contoh umum: margin 10% berarti sekitar 10 dari setiap 100 unit penjualan menjadi laba.",
            "Baca arah margin bersama pertumbuhan penjualan. Margin yang berubah dapat melibatkan biaya, pajak atau item non-operasional; data ringkas belum membuktikan penyebabnya.",
            "Perubahan margin memakai selisih poin persentase, bukan persentase pertumbuhan margin. Periksa item satu kali, pajak dan komposisi segmen sebelum membandingkan perusahaan.",
            "Tidak ada batas margin 'bagus' universal lintas sektor; modul ini belum memiliki pembanding industri.",
            [
                "Periksa operating income dan catatan pajak.",
                "Gunakan perusahaan dengan model bisnis dan periode sebanding.",
            ],
            evidence(["net_income", "revenue"], True),
            "net_income / revenue × 100",
            {
                "value": margin_change,
                "unit": "percentage points",
                "prior_period": previous["end"] if contiguous else None,
            },
        ),
        card(
            "cash_conversion",
            "Laba versus kas operasi",
            conversion,
            "×",
            f"Laba bersih {fmt(income, 'USD')}; kas operasi {fmt(cfo, 'USD')}; rasio kas operasi/laba {fmt(conversion, '×')}.",
            "Laba akuntansi berbeda dari kas yang masuk atau keluar. Arus kas operasi membantu memeriksa kas yang dihasilkan kegiatan bisnis.",
            "Jika laba dan kas bergerak berbeda, periksa piutang, persediaan, utang usaha dan transaksi nonkas. Selisih belum membuktikan manipulasi atau kualitas laba tertentu.",
            "CFO/net income hanya disajikan saat net income positif. Rekonsiliasi accrual, working capital dan klasifikasi arus kas diperlukan untuk penilaian kualitas laba.",
            "Satu periode tidak cukup untuk menilai kualitas laba. Rasio tidak dihitung saat laba nol atau negatif.",
            [
                "Bandingkan beberapa periode kas operasi.",
                "Baca rekonsiliasi laba ke kas dalam laporan arus kas.",
            ],
            evidence(["net_income", "operating_cash_flow"]),
            "operating_cash_flow / net_income, only if net_income > 0",
        ),
        card(
            "free_cash_flow",
            "Kas setelah belanja aset tetap",
            free,
            "USD",
            f"Kas operasi dikurangi pembelian properti, pabrik dan peralatan: {fmt(free, 'USD')}.",
            "Ini memperkirakan kas yang tersisa setelah kas operasi dikurangi belanja aset tetap yang tercakup dalam metrik capex ini.",
            "Nilai negatif dapat terjadi saat investasi tinggi atau kas operasi rendah. Nilai positif tidak berarti seluruhnya dapat dibagikan ke pemegang saham.",
            "Ukuran ini bukan subtotal GAAP: CFO minus PaymentsToAcquirePropertyPlantAndEquipment. Akuisisi, capitalized intangibles dan klasifikasi lain belum diselaraskan.",
            "Bukan total uang bebas dipakai; kewajiban pembiayaan dan kebutuhan bisnis lain masih perlu diperiksa.",
            [
                "Periksa besar capex dan alasan investasinya.",
                "Periksa jatuh tempo kewajiban dan kebutuhan modal kerja.",
            ],
            evidence(["operating_cash_flow", "capex"]),
            "operating_cash_flow - capex",
        ),
    ]
    assets, liabilities = val("assets"), val("liabilities")
    ratio = (
        liabilities / assets * 100
        if assets is not None and assets > 0 and liabilities is not None
        else None
    )
    cards.append(
        card(
            "liabilities_assets",
            "Konteks kewajiban di neraca",
            ratio,
            "%",
            f"Liabilitas {fmt(liabilities, 'USD')}; aset {fmt(assets, 'USD')}; liabilitas/aset {fmt(ratio, '%')}.",
            "Liabilitas adalah kewajiban perusahaan, termasuk lebih dari sekadar pinjaman bank. Aset adalah sumber daya yang diakui dalam neraca.",
            "Rasio ini memberi konteks komposisi neraca. Kemampuan membayar membutuhkan informasi kas, jatuh tempo dan arus kas; rasio ini sendiri belum menjawabnya.",
            "Liabilities/assets bukan debt/assets atau leverage regulasi. Tidak ada threshold sektoral; jangan gunakan template ini untuk menyimpulkan kesehatan bank atau perusahaan asuransi.",
            "Cash equivalents bukan seluruh likuiditas; total liabilities bukan interest-bearing debt.",
            [
                "Baca rincian utang berbunga dan jadwal jatuh tempo.",
                "Periksa aset dan kewajiban lancar sebelum menyimpulkan likuiditas.",
            ],
            evidence(["assets", "liabilities"]),
            "liabilities / assets × 100",
        )
    )
    warnings = [
        "Angka latest/as-restated; bukan informasi historis yang pasti tersedia pada tanggal periode.",
        "Analisis korporasi umum untuk AAPL/MSFT; belum memiliki modul sektoral, valuasi atau pembanding industri.",
    ]
    if not contiguous:
        warnings.append(
            "Periode pembanding tahunan berurutan tidak tersedia; insight perubahan tahunan dibatasi."
        )
    end, filed = date(year["end"]), date(analysis.get("annual_filing", {}).get("filed"))
    freshness = (
        "historical" if idx > 0 else "stale" if end and (today - end).days > 450 else "annual"
    )
    if freshness == "stale":
        warnings.append(
            "Akhir periode tahunan lebih dari 450 hari lalu. Ini ambang aplikasi, bukan penilaian kepatuhan pelaporan."
        )
    if not end or not filed or end > today or filed > today:
        return (
            [],
            warnings
            + [
                "Tanggal periode/filing tidak valid atau berada di masa depan; interpretasi diblokir."
            ],
            "blocked",
            year["end"],
            0,
            len(year.get("metrics", {})),
        )
    if (
        revenue is not None
        and old_revenue
        and growth is not None
        and growth > 0
        and margin_change is not None
        and margin_change < 0
    ):
        warnings.append(
            "Pendapatan tumbuh sementara margin turun. Ini pola angka; periksa biaya dan catatan manajemen sebelum menentukan penyebab."
        )
    present = sum(val(k) is not None for k in year.get("metrics", {}))
    return cards, warnings, freshness, year["end"], present, len(year.get("metrics", {}))


CROSS_GUIDE = {
    "us_rate": (
        "Bunga efektif AS",
        "Bunga efektif adalah suku bunga pasar uang antarbank semalam yang benar-benar teramati, bukan batas target Fed.",
        "Bandingkan dengan bunga ECB pada tanggal yang sama; dua jenis rate tersebut tidak identik.",
        "DFF merupakan effective rate, bukan target midpoint atau ekspektasi yield curve. Perbedaan rate tidak mengisolasi risk premium atau ekspektasi kebijakan.",
        "Rate saja tidak menentukan arah EURUSD.",
        [
            "Periksa rate spread dan tanggal observasinya.",
            "Baca rilis kebijakan resmi untuk konteks keputusan.",
        ],
    ),
    "ea_rate": (
        "Bunga fasilitas deposito ECB",
        "Ini bunga yang terkait dengan fasilitas simpanan semalam bank di ECB.",
        "Level rate merupakan konteks kebijakan zona euro. Dampak kurs juga bergantung pada ekspektasi dan kebijakan AS.",
        "ECB deposit facility adalah administered rate; gunakan rate yang sesuai konsep analisis sebelum membandingkannya dengan rate pasar.",
        "Angka bunga bukan prediksi kurs.",
        [
            "Bandingkan dengan bunga efektif AS pada tanggal sama.",
            "Periksa pernyataan kebijakan ECB.",
        ],
    ),
    "rate_spread": (
        "Selisih bunga AS dan zona euro",
        "Angka positif berarti bunga efektif AS lebih tinggi dari bunga deposito ECB pada tanggal yang sama; negatif berarti sebaliknya.",
        "Selisih dapat menjadi konteks perbedaan imbal hasil, tetapi ekspektasi pasar dan risiko dapat mengubah hubungannya dengan EURUSD.",
        "DFF minus ECB DFR dalam poin persentase. Basis instrumennya berbeda; bukan pure policy differential atau forward FX premium.",
        "Tidak diterjemahkan menjadi sinyal penguatan USD/EUR.",
        [
            "Periksa kedua tanggal dan jenis rate sumber.",
            "Periksa informasi pertumbuhan dan ekspektasi kebijakan yang belum dicakup panel.",
        ],
    ),
    "us_inflation": (
        "Inflasi tahunan AS",
        "YoY menunjukkan perubahan indeks harga dibanding bulan yang sama setahun sebelumnya. Positif berarti level indeks lebih tinggi dari setahun lalu.",
        "Perubahan YoY dapat dipengaruhi base effect. Kenaikan harga tidak sama dengan percepatan inflasi; diperlukan perbandingan laju antarperiode untuk menyebut percepatan.",
        "Diturunkan dari CPIAUCNS, NSA. Memerlukan exact year-ago month; ini bukan core CPI, forecast inflasi atau indikator surprise relatif konsensus.",
        "CPI AS dan HICP zona euro memakai keranjang berbeda.",
        [
            "Buka indeks CPI sumber dan bulan pembanding.",
            "Periksa komponen harga dan tanggal publikasi resmi.",
        ],
    ),
    "ea_inflation": (
        "Inflasi tahunan zona euro",
        "YoY menunjukkan perubahan HICP dibanding bulan yang sama setahun sebelumnya.",
        "Periksa pengaruh base effect dan komponen indeks; level inflasi tidak membuktikan penyebab atau langkah ECB berikutnya.",
        "HICP NSA dengan changing euro-area composition dan basis indeks 2025. Rebase dan revisi memerlukan pemeriksaan metadata serta vintage.",
        "Tidak membandingkan level indeks HICP secara langsung dengan CPI AS.",
        [
            "Baca sumber Eurostat dan bulan pembanding.",
            "Periksa komponen energi dan jasa pada rilis resmi.",
        ],
    ),
    "hash-rate": (
        "Daya komputasi penambang",
        "Hash rate memperkirakan daya komputasi penambang yang berpartisipasi menjaga jaringan Bitcoin.",
        "Baca perubahan bersama difficulty; angka ini diperkirakan dari aktivitas blok, bukan sensus mesin penambang.",
        "Estimasi TH/s dapat berisik pada jendela pendek. Periksa definisi interval provider dan jangan menganggapnya sebagai ukuran profitabilitas penambang.",
        "Hash rate meningkat tidak membuktikan harga BTC akan naik.",
        [
            "Bandingkan difficulty dan beberapa tanggal observasi.",
            "Periksa umur data sebelum menyebut kondisi jaringan saat ini.",
        ],
    ),
    "difficulty": (
        "Kesulitan penambangan",
        "Difficulty menunjukkan tingkat kesulitan untuk menemukan blok Bitcoin yang valid.",
        "Gunakan bersama hash rate dan waktu observasi untuk memahami konteks kompetisi penambangan; tidak sama dengan biaya energi.",
        "Nilai chart harian merupakan representasi provider. Perubahan sangat kecil dapat berasal dari presisi numerik atau agregasi, bukan peristiwa retarget baru.",
        "Bukan skor keamanan menyeluruh dan bukan indikator harga tunggal.",
        [
            "Bandingkan hash rate pada tanggal sebanding.",
            "Periksa data blok jika ingin meneliti retarget secara tepat.",
        ],
    ),
    "n-transactions": (
        "Aktivitas transaksi terkonfirmasi",
        "Ini jumlah transaksi Bitcoin terkonfirmasi pada observasi harian provider, bukan jumlah pengguna.",
        "Batching, pemindahan internal dan perubahan pola penggunaan dapat memengaruhi jumlah transaksi; aktivitas tidak identik dengan permintaan investasi.",
        "Transaction count bukan active entities atau settlement value. Entity adjustment dan exchange flows belum tersedia.",
        "Transaksi bertambah tidak otomatis berarti adopsi pengguna atau harga meningkat.",
        [
            "Periksa tren beberapa hari, bukan satu titik.",
            "Gunakan metrik entitas dan nilai transfer dari sumber tambahan jika tersedia.",
        ],
    ),
    "total-bitcoins": (
        "Suplai Bitcoin yang diterbitkan",
        "Ini estimasi jumlah BTC yang sudah diterbitkan, bukan jumlah koin yang tersedia untuk dijual.",
        "Pembacaan harian memakai observasi terakhir yang tersedia per hari UTC selesai. Koin hilang dan kepemilikan terkunci belum dipisahkan.",
        "Stock metric: last observed timestamp per UTC day, bukan penjumlahan/mean. Tidak menjamin midnight close; timestamp asal tetap dapat diaudit.",
        "Issued supply bukan liquid supply, free float atau realized capitalization.",
        [
            "Periksa timestamp sumber dan kebijakan sampling.",
            "Jangan memakai suplai ini sendirian untuk menyimpulkan kelangkaan pasar.",
        ],
    ),
}


def cross(analysis, symbol, today):
    metrics = analysis.get("metrics", {})
    keys = (
        ["us_rate", "ea_rate", "rate_spread", "us_inflation", "ea_inflation"]
        if symbol == "EURUSD"
        else ["hash-rate", "difficulty", "n-transactions", "total-bitcoins"]
    )
    cards, warnings, stale_count = [], [], 0
    present = 0
    for key in keys:
        metric = metrics.get(key, {})
        title, beginner, intermediate, expert, caveat, steps = CROSS_GUIDE[key]
        value, observed = number(metric.get("value")), date(metric.get("observation_date"))
        age_limit = 3 if symbol == "BTCUSD" else 75 if key.endswith("inflation") else 10
        stale = not observed or (today - observed).days > age_limit
        future = observed and observed > today
        if future:
            value = None
            stale = True
        stale_count += bool(stale)
        present += value is not None
        unit = metric.get("unit", "")
        fact = (
            f"Observasi {metric.get('observation_date') or 'tidak tersedia'}: {fmt(value, unit)}."
        )
        comparison = None
        evidence = []
        if observed:
            evidence.append(
                {
                    "metric": key,
                    "source": metric.get("source", ""),
                    "period": observed.isoformat(),
                    "url": metric.get("url"),
                    "series_id": metric.get("series_id"),
                    "source_timestamp": metric.get("observation_timestamp"),
                }
            )
        if symbol == "BTCUSD":
            # Recompute an exact-date comparison from the frozen history, not a rounded label.
            old_date = (observed - dt.timedelta(days=7)).isoformat() if observed else None
            old = next(
                (
                    number(p.get("value"))
                    for p in metric.get("history", [])
                    if p.get("date") == old_date
                ),
                None,
            )
            change = (
                (value / old - 1) * 100
                if value is not None and old is not None and old > 0
                else None
            )
            if change is not None and abs(change) < 1e-9:
                change = 0.0
            fact += f" Perubahan tujuh hari: {fmt(change, '%')}."
            comparison = {
                "value": change,
                "unit": "%",
                "prior_period": old_date if old is not None else None,
            }
            if old is not None:
                evidence.append(
                    {
                        "metric": key,
                        "source": metric.get("source", ""),
                        "period": old_date,
                        "url": metric.get("url"),
                        "series_id": metric.get("series_id"),
                    }
                )
        elif key == "rate_spread":
            for source_key in ("us_rate", "ea_rate"):
                source = metrics.get(source_key, {})
                evidence.append(
                    {
                        "metric": source_key,
                        "source": source.get("source", ""),
                        "period": metric.get("observation_date"),
                        "url": source.get("url"),
                        "series_id": source.get("series_id"),
                    }
                )
        elif key.endswith("inflation"):
            source_key = "us_cpi" if key == "us_inflation" else "ea_hicp"
            source = metrics.get(source_key, {})
            if observed:
                previous = observed.replace(year=observed.year - 1, day=1).isoformat()
                for label in (observed.isoformat(), previous):
                    evidence.append(
                        {
                            "metric": source_key,
                            "source": source.get("source", ""),
                            "period": label,
                            "url": source.get("url"),
                            "series_id": source.get("series_id"),
                        }
                    )
        item = card(
            key,
            title,
            value,
            unit,
            fact,
            beginner,
            intermediate,
            expert,
            caveat,
            steps,
            evidence,
            metric.get("formula")
            or ("(value / exact seven-days-ago value - 1) × 100" if symbol == "BTCUSD" else None),
            comparison,
        )
        item.update(
            stale=bool(stale),
            observation_date=metric.get("observation_date"),
            issue=(
                "Tanggal observasi di masa depan; nilai disembunyikan."
                if future
                else metric.get("issue")
            ),
        )
        cards.append(item)
    if stale_count:
        warnings.append(
            f"{stale_count} dari {len(keys)} metrik sudah terlambat atau tanggalnya tidak tersedia. Insight menjelaskan periode observasi, bukan kondisi pasar saat ini."
        )
    if symbol == "EURUSD":
        warnings += [
            "Tanggal observasi bukan tanggal publikasi. Perbandingan rate dan inflasi memiliki frekuensi berbeda.",
            "Belum ada GDP, tenaga kerja, ekspektasi pasar atau surprise terhadap konsensus; konteks makro belum lengkap.",
        ]
    else:
        warnings.append(
            "Belum ada exchange flow, entity adjustment, realized cap atau data profitabilitas penambang."
        )
    return (
        cards,
        warnings,
        "stale" if stale_count == len(keys) else "mixed" if stale_count else "current",
        None,
        present,
        len(keys),
    )


def build(payload, symbol, period=None, now=None):
    if symbol not in SUPPORTED:
        raise ValueError("Unsupported fundamental insight symbol")
    if period and symbol in ("EURUSD", "BTCUSD"):
        raise ValueError("Annual period selection only applies to equity insights")
    today = (now or dt.datetime.now(dt.timezone.utc)).date()
    base = {
        "version": VERSION,
        "symbol": symbol,
        "language": "id",
        "snapshot_id": payload.get("snapshot_id"),
        "fetched_at": payload.get("fetched_at"),
        "as_of": today.isoformat(),
        "has_data": bool(payload.get("has_data")),
        "engine": "Deterministic rules / no LLM",
        "cards": [],
        "visuals": [],
        "period": None,
        "warnings": [
            "Penjelasan edukatif berbasis angka tersimpan; bukan prediksi harga, rating investasi atau rekomendasi transaksi."
        ],
    }
    if not base["has_data"] or not payload.get("analysis"):
        base.update(
            summary="Belum ada bukti tersimpan untuk dijelaskan. Sinkronkan fundamental aset ini terlebih dahulu.",
            quality={
                "freshness": "no_data",
                "available": 0,
                "expected": 0,
                "label": "Belum ada data",
            },
            questions=[],
        )
        return base
    analysis = payload["analysis"]
    cards, warnings, freshness, selected, available, expected = (
        equity(analysis, period, today)
        if symbol in ("AAPL", "MSFT")
        else cross(analysis, symbol, today)
    )
    if available == 0 and freshness != "blocked":
        freshness = "incomplete"
    labels = {
        "historical": "Periode historis dipilih",
        "annual": "Laporan tahunan / periksa periode",
        "stale": "Observasi terlambat",
        "mixed": "Kesegaran data beragam",
        "current": "Dalam ambang kesegaran aplikasi",
        "blocked": "Interpretasi diblokir",
        "incomplete": "Nilai belum tersedia untuk interpretasi",
    }
    missing = sum(c["value"] is None for c in cards)
    if missing:
        warnings.append(
            f"{missing} insight tidak memiliki nilai yang dapat dihitung; penjelasan konsep tetap tersedia tanpa kesimpulan numerik."
        )
    if (payload.get("last_job") or {}).get("status") in ("failed", "interrupted"):
        warnings.append(
            "Sinkronisasi terakhir gagal atau terputus; snapshot terakhir yang berhasil tetap digunakan."
        )
    scenarios = {
        "equity": [
            {
                "condition": "Jika pendapatan tumbuh dan margin turun",
                "reading": "Periksa biaya, pajak, bauran produk dan item non-operasional. Pola ini belum menjelaskan penyebabnya.",
                "check": "Filing MD&A dan catatan segmen/pajak; belum diekstrak aplikasi.",
            },
            {
                "condition": "Jika laba positif tetapi kas operasi lebih rendah",
                "reading": "Periksa working capital dan item nonkas. Ini pertanyaan investigasi, bukan tuduhan masalah akuntansi.",
                "check": "Rekonsiliasi laporan arus kas dan catatan piutang/persediaan.",
            },
        ],
        "EURUSD": [
            {
                "condition": "Jika selisih bunga berubah",
                "reading": "Periksa apakah kedua rate berada pada tanggal yang sama dan apakah konsep instrumennya sebanding. Jangan langsung menyimpulkan arah kurs.",
                "check": "Keputusan kebijakan, ekspektasi pasar dan data pertumbuhan tambahan.",
            },
            {
                "condition": "Jika inflasi YoY berubah",
                "reading": "Pisahkan perubahan level harga dari perubahan laju inflasi; periksa base effect.",
                "check": "Bulan pembanding dan komponen CPI/HICP pada rilis resmi.",
            },
        ],
        "BTCUSD": [
            {
                "condition": "Jika hash rate dan difficulty bergerak berbeda",
                "reading": "Periksa perbedaan jendela estimasi dan tanggal; data chart belum membuktikan perubahan profitabilitas penambang.",
                "check": "Timestamp, data blok dan biaya penambang dari sumber tambahan.",
            },
            {
                "condition": "Jika transaksi meningkat",
                "reading": "Periksa batching dan jenis aktivitas sebelum menganggap jumlah pengguna bertambah.",
                "check": "Entity-adjusted activity dan nilai settlement; belum tersedia di aplikasi.",
            },
        ],
    }
    base["highlights"] = [c["fact"] for c in cards if c["value"] is not None][:3]
    base["scenarios"] = scenarios["equity" if symbol in ("AAPL", "MSFT") else symbol]
    base.update(
        cards=cards,
        period=selected,
        warnings=base["warnings"] + warnings,
        quality={
            "freshness": freshness,
            "label": labels[freshness],
            "available": available,
            "expected": expected,
            "meaning": "Cakupan dan kesegaran data; bukan probabilitas kebenaran interpretasi atau peluang harga naik.",
        },
        summary=f"{len(cards)} sudut baca untuk {symbol}"
        + (
            f" pada periode berakhir {selected}."
            if selected
            else "; setiap metrik dibaca menurut tanggal observasinya."
        ),
        questions=[
            "Apa yang berubah pada periode yang dapat dibandingkan?",
            "Apakah metrik pendamping mendukung pembacaan ini?",
            "Bukti tambahan apa yang belum tersedia sebelum menarik kesimpulan?",
        ],
    )
    if freshness != "blocked":
        base["visuals"] = fundamental_visuals.build(analysis, symbol, selected, today)
    return base
