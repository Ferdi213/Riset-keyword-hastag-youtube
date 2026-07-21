#!/usr/bin/env python3
"""
YouTube Keyword & Hashtag Finder
=================================
Tool buat riset keyword yang lagi dicari orang di YouTube, plus hashtag
yang beneran dipakai video-video top di niche tertentu.

CARA PAKAI CEPAT
-----------------
1) Mode GRATIS (tanpa API key) - cuma keyword suggestion:
   python yt_keyword_hashtag_finder.py --keywords "resep ayam" "tutorial excel"

2) Mode LENGKAP (butuh YouTube Data API key gratis) - keyword + hashtag +
   analisis video top performer:
   python yt_keyword_hashtag_finder.py --keywords "resep ayam" --api-key YOUR_API_KEY

3) Mode VERIFIKASI HASHTAG (butuh API key) - cek satu-satu apakah hashtag
   itu BENERAN dipakai di video nyata + seberapa rame (jumlah video & views):
   python yt_keyword_hashtag_finder.py --verify-hashtags github githubpages webdev ngoding --api-key YOUR_API_KEY

CARA DAPETIN API KEY GRATIS
----------------------------
1. Buka https://console.cloud.google.com/
2. Buat project baru (atau pakai yang sudah ada)
3. Aktifkan "YouTube Data API v3" di menu APIs & Services > Library
4. Buat credential jenis "API Key" di APIs & Services > Credentials
5. Copy API key-nya, tempel di --api-key atau simpan sebagai env var YT_API_KEY

Kuota gratis defaultnya 10.000 unit/hari. Search = 100 unit/panggilan,
videos.list = 1 unit/panggilan, jadi cukup buat riset harian yang lumayan banyak.
"""

import argparse
import csv
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import json
from collections import Counter

HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)


# ---------------------------------------------------------------------------
# 1) KEYWORD SUGGESTION (gratis, tanpa API key) — pakai endpoint autocomplete
#    yang sama dengan yang dipakai kolom search YouTube.
# ---------------------------------------------------------------------------
def get_autocomplete_suggestions(seed_keyword: str, hl: str = "id", gl: str = "ID") -> list:
    """Ambil daftar auto-suggestion YouTube untuk satu seed keyword."""
    params = {
        "client": "firefox",
        "ds": "yt",
        "q": seed_keyword,
        "hl": hl,
        "gl": gl,
    }
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data[1] if len(data) > 1 else []
    except Exception as e:
        print(f"  [!] Gagal ambil suggestion untuk '{seed_keyword}': {e}", file=sys.stderr)
        return []


def expand_keywords(seed_keywords: list, deep: bool = False) -> list:
    """
    Perluas seed keyword jadi puluhan variasi.
    Kalau deep=True, tambahin tiap huruf a-z di belakang seed buat
    'memancing' lebih banyak suggestion (teknik 'alphabet soup').
    """
    all_suggestions = set()
    for seed in seed_keywords:
        print(f"[*] Mencari suggestion untuk: '{seed}'")
        base = get_autocomplete_suggestions(seed)
        all_suggestions.update(base)

        if deep:
            for letter in "abcdefghijklmnopqrstuvwxyz":
                variant = f"{seed} {letter}"
                suggestions = get_autocomplete_suggestions(variant)
                all_suggestions.update(suggestions)
                time.sleep(0.15)  # sopan-sopan ke server, jangan spam request

    return sorted(all_suggestions)


# ---------------------------------------------------------------------------
# 2) ANALISIS VIDEO TOP-PERFORMER (butuh API key) — cari video top untuk
#    keyword, ambil statistik + tag tersembunyi + hashtag dari judul/deskripsi
# ---------------------------------------------------------------------------
def youtube_api_get(endpoint: str, params: dict, api_key: str) -> dict:
    params["key"] = api_key
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_top_videos(keyword: str, api_key: str, max_results: int = 15,
                       region_code: str = "ID", published_within_days: int = 90) -> list:
    """Cari video paling relevan+populer untuk sebuah keyword."""
    from datetime import datetime, timedelta, timezone
    published_after = (datetime.now(timezone.utc) - timedelta(days=published_within_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "order": "viewCount",
        "maxResults": min(max_results, 50),
        "regionCode": region_code,
        "publishedAfter": published_after,
    }
    try:
        data = youtube_api_get("search", params, api_key)
    except Exception as e:
        print(f"  [!] Search API error untuk '{keyword}': {e}", file=sys.stderr)
        return []
    return [item["id"]["videoId"] for item in data.get("items", []) if "videoId" in item.get("id", {})}


def get_video_details(video_ids: list, api_key: str) -> list:
    """Ambil statistik (views/likes) + tags + description buat list video ID."""
    if not video_ids:
        return []
    details = []
    # API cuma bisa 50 ID per request
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        params = {"part": "snippet,statistics", "id": ",".join(chunk)}
        try:
            data = youtube_api_get("videos", params, api_key)
        except Exception as e:
            print(f"  [!] Videos API error: {e}", file=sys.stderr)
            continue
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            details.append({
                "video_id": item.get("id"),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "view_count": int(stats.get("viewCount", 0)),
                "channel": snippet.get("channelTitle", ""),
            })
    return details


def extract_hashtags(text: str) -> list:
    return [f"#{tag}" for tag in HASHTAG_RE.findall(text)]


def analyze_keyword(keyword: str, api_key: str, max_results: int = 25) -> dict:
    """
    Gabungkan search + detail + hashtag jadi satu ringkasan per keyword.
    """
    print(f"[*] Menganalisis video top untuk: '{keyword}'")
    video_ids = search_top_videos(keyword, api_key, max_results=max_results)
    details = get_video_details(video_ids, api_key)

    hashtag_views = {}   # hashtag -> list of view_count dari video yang pakai
    tag_counter = Counter()
    total_views = 0

    for v in details:
        total_views += v["view_count"]
        seen_in_this_video = set(h.lower() for h in extract_hashtags(v["title"] + " " + v["description"]))
        for h in seen_in_this_video:
            hashtag_views.setdefault(h, []).append(v["view_count"])
        for t in v["tags"]:
            tag_counter[t.lower()] += 1

    hashtag_stats = []
    for tag, views_list in hashtag_views.items():
        hashtag_stats.append({
            "hashtag": tag,
            "video_count": len(views_list),
            "avg_views": round(sum(views_list) / len(views_list)),
            "total_views": sum(views_list),
            "max_views": max(views_list),
        })
    # urutkan hashtag dari yang paling "rame" (total views tertinggi)
    hashtag_stats.sort(key=lambda x: -x["total_views"])

    return {
        "keyword": keyword,
        "video_sample_size": len(details),
        "avg_views": round(total_views / len(details)) if details else 0,
        "hashtag_stats": hashtag_stats,
        "top_hidden_tags": tag_counter.most_common(20)
    }


# ---------------------------------------------------------------------------
# 3) FITUR VERIFIKASI HASHTAG SPESIFIK
# ---------------------------------------------------------------------------
def verify_specific_hashtags(hashtags: list, api_key: str) -> list:
    """Memverifikasi hashtag dari config file langsung ke pencarian YouTube."""
    results = []
    for ht in hashtags:
        clean_ht = ht.replace("#", "")
        print(f"[*] Memverifikasi performa tren hashtag: #{clean_ht}")
        params = {
            "part": "snippet",
            "q": f"#{clean_ht}",
            "type": "video",
            "maxResults": 5,
        }
        try:
            data = youtube_api_get("search", params, api_key)
            total_results = data.get("pageInfo", {}).get("totalResults", 0)
            results.append({
                "hashtag": f"#{clean_ht}",
                "estimated_reach_score": total_results
            })
        except Exception as e:
            print(f"  [!] Gagal memverifikasi hashtag #{clean_ht}: {e}", file=sys.stderr)
        time.sleep(0.2)
    return results


# ---------------------------------------------------------------------------
# 4) MAIN APPLICATION ENTRYPOINT & EXPORTER
# ---------------------------------------------------------------------------
def read_lines_from_file(filepath: str) -> list:
    """Helper untuk membaca kata kunci/hashtag per baris dari folder config/"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def main():
    parser = argparse.ArgumentParser(description="YouTube Keyword & Hashtag Finder")
    parser.add_argument("--keywords", nargs="+", help="Keyword langsung via terminal")
    parser.add_argument("--verify-hashtags", nargs="+", help="Hashtag langsung via terminal")
    parser.add_argument("--api-key", help="YouTube Data API v3 Key")

parser.add_argument("--deep", action="store_true", help="Gunakan mode alphabet soup")

args = parser.parse_args()
api_key = args.api_key or os.environ.get("YT_API_KEY")

# Ambil data input dari file txt di folder config/ (sesuai struktur repositori Anda)
file_keywords = read_lines_from_file("config/keywords.txt")
file_hashtags = read_lines_from_file("config/hashtags.txt")

# Gabungkan input CLI parameter dan isi File TXT
target_keywords = (args.keywords or []) + file_keywords
target_hashtags = (args.verify-hashtags or []) + file_hashtags

os.makedirs("results", exist_ok=True)

if not target_keywords and not target_hashtags:
print("[!] Tidak ada kata kunci atau hashtag ditemukan di terminal maupun di folder 'config/'.")
print("[*] Berjalan dalam mode demo otomatis...")
target_keywords = ["resep masakan"]

# JALAN 1: Eksekusi Riset Keyword
if target_keywords:
print("\n=== MEMULAI RISET KEYWORD SUGGESTION ===")
expanded = expand_keywords(target_keywords, deep=args.deep)

with open("results/keyword_suggestions.csv", "w", encoding="utf-8", newline="") as f:
writer = csv.writer(f)
writer.writerow(["Keyword Suggestion"])
for kw in expanded:
writer.writerow([kw])
print(f"[✓] Berhasil menyimpan {len(expanded)} ide keyword ke 'results/keyword_suggestions.csv'")

# Jika API Key aktif, lakukan Deep Analysis Kompetitor
if api_key:
print("\n=== MEMULAI ANALISIS KOMPETITOR VIA YOUTUBE API ===")
for kw in target_keywords:
analysis = analyze_keyword(kw, api_key)

# Simpan analisis hashtag kompetitor
filename_ht = f"results/analysis_hashtags_{kw.replace(' ', '_')}.csv"
with open(filename_ht, "w", encoding="utf-8", newline="") as f:
writer = csv.DictWriter(f, fieldnames=["hashtag", "video_count", "avg_views", "total_views", "max_views"])
writer.writeheader()
writer.writerows(analysis["hashtag_stats"])

# Simpan analisis tag tersembunyi kompetitor
filename_tags = f"results/analysis_tags_{kw.replace(' ', '_')}.csv"
with open(filename_tags, "w", encoding="utf-8", newline="") as f:
writer = csv.writer(f)
writer.writerow(["Tag", "Frequency Count"])
writer.writerows(analysis["top_hidden_tags"])

print("[✓] Analisis mendalam video kompetitor sukses diekspor ke folder 'results/'.")
else:
print("\n[!] Lewati analisis kompetitor karena YT_API_KEY tidak dikonfigurasi.")

# JALAN 2: Eksekusi Verifikasi Daftar Hashtag
if target_hashtags:
if not api_key:
print("\n[!] Fitur verifikasi hashtag membutuhkan API Key untuk bekerja.")
else:
print("\n=== MEMULAI VERIFIKASI TREN HASHTAG ===")
verified_data = verify_specific_hashtags(target_hashtags, api_key)
with open("results/verified_hashtags.csv", "w", encoding="utf-8", newline="") as f:
writer = csv.DictWriter(f, fieldnames=["hashtag", "estimated_reach_score"])
writer.writeheader()
writer.writerows(verified_data)
print("[✓] Berhasil memverifikasi tren hashtag ke 'results/verified_hashtags.csv'")

if name == "main":
main()

