# YouTube Keyword & Hashtag Finder

Script Python buat riset kata kunci yang lagi dicari orang di YouTube, sekaligus
lihat hashtag & tag tersembunyi yang beneran dipakai video-video top di niche kamu.

Cuma pakai library bawaan Python (tidak perlu `pip install` apapun) — tinggal
jalankan dengan Python 3.

  file config/seed_keyword.text : untuk cari kata kunci di kolom pencarian 


  
## Cara Pakai

### Mode 1 — Gratis, tanpa API key (keyword suggestion doang)
```bash
python yt_keyword_hashtag_finder.py --keywords "resep ayam" "tutorial excel"
```
Ini bakal ngambil auto-suggestion dari kolom pencarian YouTube — cara paling akurat
buat tahu apa yang orang beneran ketik di YouTube.

Tambahin `--deep` kalau mau hasil lebih banyak (nyoba kombinasi seed + a-z):
```bash
python yt_keyword_hashtag_finder.py --keywords "resep ayam" --deep
```

### Mode 2 — LANGSUNG dapat hashtag + views, cukup kasih keyword
```bash
python yt_keyword_hashtag_finder.py --keywords "resep ayam" --api-key ISI_API_KEY_KAMU --csv hasil.csv
```
Ini yang paling sering kamu butuh: **cukup kasih keyword, ga perlu nebak-nebak
hashtag duluan.** Script bakal:
1. Cari video paling populer (published 90 hari terakhir) untuk keyword itu
2. Baca hashtag yang BENERAN dipakai di judul & deskripsi video-video itu
3. Hitung avg views & total views dari video yang pakai tiap hashtag
4. Urutkan hashtag dari yang paling rame (total views tertinggi)

Contoh output buat keyword "resep ayam":
```
Hashtag ditemukan, diurutkan dari yang paling rame:
   HASHTAG                  DIPAKAI DI    AVG VIEWS      TOTAL VIEWS
   #resepayam               8 video          450,000       3,600,000
   #masakanrumahan          5 video          280,000       1,400,000
   #kuliner                 3 video           90,000         270,000
```
Artinya `#resepayam` paling worth dipakai — banyak video top yang pakai DAN
views-nya tinggi.

### Mode 3 — Verifikasi hashtag spesifik (kalau kamu sudah punya kandidat sendiri)
```bash
python yt_keyword_hashtag_finder.py --verify-hashtags github githubpages tutorialgithub webdev ngoding belajarcoding --api-key ISI_API_KEY_KAMU --csv verifikasi.csv
```
Ini yang paling penting kalau kamu mau bikin "tools SEO" beneran. Buat tiap hashtag,
script akan:
1. Search YouTube pakai hashtag itu (persis kayak orang search manual)
2. Cek video-video yang **genuinely** menyertakan hashtag itu di judul/deskripsi
   (bukan cuma loose-match dari algoritma search)
3. Hitung rata-rata views & views tertinggi dari sample video tersebut
4. Kasih verdict: **RAME** (avg views ≥100rb, kompetisi ketat) / **CUKUP RAME**
   (≥10rb, peluang masih ada) / **SEPI-SEDANG** (≥1rb, cocok channel kecil) /
   **SANGAT SEPI** (di bawah itu — hati-hati)
5. Kalau hashtag-nya sama sekali ga ketemu video yang pakai → statusnya
   `TIDAK DITEMUKAN`, jangan dipakai

Ini bukti langsung dari data YouTube (views real), bukan tebakan dari artikel
SEO — jawaban yang lebih akurat dari yang aku kasih manual kemarin.

### Cara dapetin API key (gratis)
1. Buka https://console.cloud.google.com/
2. Buat project baru
3. Aktifkan **YouTube Data API v3** di *APIs & Services > Library*
4. Buat credential **API Key** di *APIs & Services > Credentials*
5. Pakai lewat `--api-key`, atau simpan sebagai environment variable `YT_API_KEY`

Kuota gratis: 10.000 unit/hari. Satu keyword analysis pakai sekitar 100 unit,
jadi cukup buat riset ~90 keyword/hari.

> **Catatan:** script ini butuh koneksi internet ke `googleapis.com` dan
> `suggestqueries.google.com`. Jalankan di laptop/komputer kamu sendiri —
> di sandbox ini aku cuma bisa nulis & cek sintaksnya, tapi belum bisa run
> live karena aksesnya dibatasi.

---

## Contoh hasil riset (referensi umum, per Juli 2026)

Sebagai gambaran sambil kamu siapin API key, ini pola yang lagi kepake luas
di YouTube 2026 berdasarkan riset:

**Hashtag "evergreen" berkekuatan tinggi** (aman dipakai hampir semua niche):
`#shorts` `#viral` `#youtubeshorts` `#fyp` `#trending` `#dance` `#music` `#ai` `#money` `#funny`

**Formula racikan hashtag yang disaranin:**
- 70% hashtag niche/evergreen (buat jangkauan konsisten ke audiens inti)
- 30% hashtag trending (buat ledakan sesekali ke audiens baru)
- Total 3–5 hashtag per video — jangan kebanyakan, di atas ~15 malah bisa nurunin performa
- 3 hashtag pertama di deskripsi bakal muncul sebagai link di atas judul → taruh yang paling kuat di situ

**Cara manual cepat kalau lagi buru-buru:** ketik `#` diikuti topik kamu langsung
di kolom search YouTube — auto-suggest yang muncul itu hashtag yang lagi beneran
rame buat topik tersebut saat ini juga.

*(Data di atas dari riset web umum, bukan hasil live run script — jalankan
scriptnya dengan API key buat dapet angka & hashtag yang spesifik ke niche kamu.)*
