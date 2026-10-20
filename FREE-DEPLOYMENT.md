# Deployment gratis: GitHub Actions + Vercel Hobby

Gunakan panduan ini sebagai pengganti langkah Render/Oracle dalam DEPLOYMENT.md.
Versi ini melanjutkan deployment dan Windows test cleanup yang sudah ada.
Perubahan dikembangkan di feature/v2; backup/v1 tetap menyimpan versi sebelumnya.
Merge feature/v2 ke main setelah validasi, sebelum menjalankan workflow terjadwal.
Tidak membutuhkan akun Render/Oracle, kartu, backend URL, atau backend token.

## Cara kerja dan batasnya

GitHub Actions menjalankan Python sampai selesai setiap enam jam, bukan server 24 jam.
Workflow membaca snapshot publik sebelumnya, mengambil provider, menghitung forecast dan
insight, kemudian menyimpan JSON ke branch market-data. Vercel membacanya dengan cache
sekitar lima menit. Tidak ada redeploy frontend untuk pembaruan data.

Jadwal 00:17, 06:17, 12:17, 18:17 UTC (07:17, 13:17, 19:17, 01:17 WIB).
GitHub dapat menunda atau melewatkan jadwal saat sibuk. Workflow publik dapat dinonaktifkan
setelah 60 hari tanpa aktivitas repository; periksa tab Actions dan aktifkan kembali jika perlu.
Jalankan manual untuk percobaan ulang; versi ini tidak mempertahankan retry 30 menit.
Cache frontend dan upstream GitHub bisa menambah keterlambatan beberapa menit.

Demo tetap read-only. Model trend/naive dan horizon 1/7/14/30 dihitung sebelumnya.
Grafik dan insight Beginner/Intermediate/Expert tetap tersedia untuk AAPL/MSFT, EURUSD, BTCUSD.
Hanya dataset dan snapshot fundamental terkini per aset yang diterbitkan; periode tahunan
pada snapshot tersebut tetap dapat dipilih. Riwayat eksperimen/dataset lokal tidak dipindahkan.
Jika provider gagal, kelompok data sebelumnya dipertahankan. Tanggal observasi dan kegagalan
terlihat; waktu pembuatan bundle bukan tanggal observasi provider. Snapshot lebih dari 12 jam
mendapat peringatan di panel automation. Jika semua pengambilan awal gagal, tidak ada publikasi.
Tidak ada fallback harga sintetis dalam workflow production.

## 1. Terapkan dan cek lokal

Dari CMD di root proyek, sesudah kedua server dihentikan:

    git apply --check signal-free-scheduled-deployment.patch
    git apply signal-free-scheduled-deployment.patch
    .venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
    cd frontend
    node scripts/check-snapshots.cjs
    node scripts/check-deployment-proxy.cjs
    npx tsc --noEmit
    npm run build
    cd ..

Tinjau git status. Jangan stage .env asli, database, .venv-market, node_modules, atau patch.
Commit file kode baru dan workflow lalu push ke main. Tidak perlu menghapus patch deployment
sebelumnya. render.yaml tidak digunakan; jangan membuat Blueprint Render.

## 2. Repository dan secret GitHub

Alur ini membutuhkan repository PUBLIK agar Vercel dapat membaca branch market-data tanpa
credential tambahan. Jangan mengubah repository privat menjadi publik tanpa meninjau seluruh
isi dan riwayatnya. Jika perlu mempertahankan kode privat, konfigurasi ini perlu disesuaikan.
Snapshot hanya berisi data yang memang hendak ditampilkan ke pengunjung.

GitHub repository > Settings > Secrets and variables > Actions > New repository secret:

- ALPHAVANTAGE_API_KEY: key asli untuk data harga.
- FRED_API_KEY: key asli untuk macro EURUSD.
- SEC_USER_AGENT: nama aplikasi dan email kontak asli untuk SEC.

Jangan menaruh key dalam file YAML, Repository Variables, atau NEXT_PUBLIC_*.
Jangan menyalin SSL_CERT_FILE Windows ke workflow Linux.
Secret hanya diberikan ke langkah pengambilan provider. Database sementara dan respons mentah
provider tidak disimpan ke branch. Exporter menolak credential terkonfigurasi pada hasil JSON.

## 3. Jalankan pembaruan awal

GitHub > Actions > Refresh public market snapshots > Run workflow > branch main.
Tunggu selesai; timeout maksimal 20 menit. Ada jeda untuk menghormati cooldown connector.
Periksa log "Fetch providers and build normalized snapshot": status updated/retained/unavailable
tersedia per aset. Centang hijau berarti publikasi selesai, bukan semua provider pasti berhasil.

Branch market-data akan berisi bundle.json dan konfigurasi untuk menonaktifkan deploy branch
tersebut. Branch ini dikelola workflow; jangan merge ke main atau mengeditnya manual.
Buka bundle.json untuk memastikan aset dan tanggal data sudah sesuai.

Jika push 403: periksa Settings > Actions > General > Workflow permissions dan aturan branch.
Workflow meminta contents: write. Jika kebijakan repository menolak, izinkan workflow resmi
ini menulis branch market-data; jangan membagikan personal access token sebagai jalan pintas.
Jika provider menolak IP runner atau batas API tercapai, log menunjukkan unavailable/retained.
Jangan menghapus snapshot terakhir atau menganggap kegagalan itu data kosong yang valid.

## 4. Vercel

Add New > Project > import repository > pilih paket Hobby untuk demo personal/nonkomersial.
Framework Next.js; Root Directory frontend; Install npm ci; Build npm run build;
Output Directory default; Production Branch main.

Environment variables untuk Production:

    DEPLOYMENT_MODE=snapshot
    SNAPSHOT_REPOSITORY=OWNER/NAMA-REPOSITORY

Misalnya hanya jika alamat GitHub-mu memang demikian:

    SNAPSHOT_REPOSITORY=JackButler99/market-lab

Jangan memasukkan URL lengkap, .git, /tree/main atau /market-data.
BACKEND_URL, BACKEND_API_TOKEN, NEXT_PUBLIC_API_URL tidak diperlukan untuk mode ini.
Provider keys tetap hanya di GitHub Secrets, bukan di Vercel.
Klik Deploy. Jika environment berubah, redeploy frontend.
Aktifkan Preview environment hanya jika ingin preview membaca snapshot yang sama.

## 5. Verifikasi

- /api/dashboard pada domain Vercel menghasilkan JSON dengan dataset_id, bukan 503.
- /api/snapshot-status menunjukkan generated_at serta snapshot_stale.
- Automation menampilkan Scheduled snapshots, bukan klaim worker Python aktif.
- Pilih tiap aset, model/horizon dan periode tahunan; buka grafik serta ketiga mode insight.
- Harga dan fundamental bisa memiliki tanggal berbeda; periksa masing-masing.
- Jalankan workflow manual lagi; setelah cache berlalu, snapshot baru terlihat tanpa redeploy.
- Matikan server lokal; aplikasi Vercel tetap bisa membaca snapshot.
- POST/import/sync manual publik tetap diblokir. Gunakan Run workflow untuk refresh admin.

503: periksa dua environment Vercel, visibility repo, branch market-data dan workflow pertama.
409 saat insight: snapshot berubah ketika tab terbuka; muat ulang halaman/tab.
Tidak ada aset: provider belum berhasil; cek secret, kuota dan akses dari runner.

GitHub Actions standard runner gratis untuk repository publik. Vercel Hobby memiliki kuota dan
batas personal/nonkomersial; penggunaan melampaui kuota dapat menghentikan layanan.
Ini tidak menjamin uptime, eksekusi tepat waktu, atau akses provider dari IP GitHub.

Dokumentasi:
https://docs.github.com/en/billing/concepts/product-billing/github-actions
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
https://vercel.com/docs/plans/hobby
