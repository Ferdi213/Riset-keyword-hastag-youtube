# Setup GitHub Actions — Riset Keyword & Hashtag Otomatis

## Struktur folder
```
repo-kamu/
├── .github/
│   └── workflows/
│       └── yt-keyword-research.yml   ← workflow-nya, jangan diedit kalau belum paham
├── config/
│   ├── keywords.txt                  ← EDIT INI buat ganti daftar keyword
│   └── hashtags.txt                  ← EDIT INI buat ganti daftar hashtag
├── results/
│   └── (hasil riset otomatis nongol di sini tiap workflow jalan)
└── scripts/
    └── yt_keyword_hashtag_finder.py  ← script utamanya, jangan diedit kalau belum paham
```

## Langkah setup (5 menit)

### 1. Bikin repo baru (atau pakai yang sudah ada)
Upload semua folder di atas ke repo GitHub kamu — bisa lewat drag & drop di
web GitHub, atau `git push` kalau udah familiar terminal.

### 2. Simpan API key sebagai Secret (WAJIB, biar aman)
Jangan pernah taruh API key langsung di file config atau workflow — pasti
bakal ketauan publik. Simpan lewat GitHub Secrets:

1. Buka repo kamu di GitHub
2. **Settings** → **Secrets and variables** → **Actions**
3. Klik **New repository secret**
4. Name: `YT_API_KEY`
5. Value: (paste API key YouTube Data API v3 kamu)
6. **Add secret**

### 3. Edit daftar keyword & hashtag
Buka `config/keywords.txt` dan `config/hashtags.txt` langsung di GitHub
(klik file → pensil edit), tambah/hapus baris sesuai kebutuhan, commit.
Ga perlu sentuh file workflow atau script sama sekali.

### 4. Jalankan pertama kali (manual, buat testing)
1. Buka tab **Actions** di repo kamu
2. Pilih workflow **"Riset Keyword & Hashtag YouTube"** di sidebar kiri
3. Klik **Run workflow** → **Run workflow** (tombol hijau)
4. Tunggu ~1-2 menit, refresh halaman
5. Kalau sukses (centang hijau), cek folder `results/` — bakal ada file CSV baru

### 5. Selesai — jalan otomatis tiap minggu
Setelah itu workflow jalan sendiri tiap Senin jam 07:00 WIB, hasilnya
otomatis ke-commit ke folder `results/`. Mau ganti jadwalnya, edit baris
`cron` di file workflow — format & contohnya ada di komentar file itu.

## Kalau workflow gagal (merah)
Klik run yang gagal → klik step yang merah → baca error message-nya.
Penyebab paling umum:
- **API key salah/belum di-set** → cek lagi Secret `YT_API_KEY` di step 2
- **Kuota API habis** (limit 10.000 unit/hari) → tunggu besok atau bikin
  project Google Cloud baru
- **Format `config/keywords.txt` atau `hashtags.txt` salah** → pastikan
  satu item per baris, tanpa tanda kutip

## Catatan soal biaya
GitHub Actions gratis untuk repo publik (unlimited minutes). Untuk repo
privat, gratis 2.000 menit/bulan — workflow ini cuma makan ~1-2 menit per
run, jadi jalan mingguan jauh dari batas itu.
