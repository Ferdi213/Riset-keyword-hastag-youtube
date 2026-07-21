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
1. Buka https://google.com
2. Buat project baru (atau pakai yang sudah ada)
3. Aktifkan "YouTube Data API v3" di menu APIs & Services > Library
4. Buat credential jenis "API Key" di APIs & Services > Credentials
5. Copy API key-nya, tempel di --api-key atau simpan sebagai env var YT_API_KEY
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
# 1) KEYWORD SUGGESTION (gratis, tanpa API key)
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
    url = "https://google.com?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data[1] if len(data) > 1 else []
    except Exception as e:
        print(f"[-] Gagal mengambil suggestion untuk '{seed_keyword}': {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# 2) YOUTUBE DATA API V3 FUNCTIONS (Butuh API Key)
# ---------------------------------------------------------------------------
def call_youtube_api(endpoint: str, params: dict) -> dict:
    """Helper untuk memanggil YouTube Data API v3 via REST."""
    url = f"https://googleapis.com{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[-] API Error pada endpoint [{endpoint}]: {e}", file=sys.stderr)
        return {}


def get_top_videos_by_keyword(keyword: str, api_key: str, max_results: int = 10) -> list:
    """Mencari video teratas berdasarkan keyword untuk diambil video ID-nya."""
    print(f"[+] Mencari {max_results} video teratas untuk keyword: '{keyword}'...")
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "maxResults": max_results,
        "key": api_key
    }
    res = call_youtube_api("search", params)
    video_ids = []
    if "items" in res:
        for item in res["items"]:
            v_id = item.get("id", {}).get("videoId")
            if v_id:
                video_ids.append(v_id)
    return video_ids


def get_video_details(video_ids: list, api_key: str) -> list:
    """Mengambil tags, hashtag dari deskripsi, dan performa (views) dari daftar Video ID."""
    if not video_ids:
        return []
    
    print(f"[+] Mengambil detail data untuk {len(video_ids)} video...")
    params = {
        "part": "snippet,statistics",
        "id": ",".join(video_ids),
        "key": api_key
    }
    res = call_youtube_api("videos", params)
    
    video_data = []
    if "items" in res:
        for item in res["items"]:
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            tags = snippet.get("tags", [])
            view_count = int(stats.get("viewCount", 0))
            
            # Ekstrak hashtag unik dari deskripsi menggunakan Regex
            hashtags_found = list(set(HASHTAG_RE.findall(description.lower())))
            
            video_data.append({
                "title": title,
                "views": view_count,
                "tags": tags,
                "hashtags": hashtags_found
            })
    return video_data


# ---------------------------------------------------------------------------
# 3) FITUR VERIFIKASI HASHTAG
# ---------------------------------------------------------------------------
def verify_hashtags_on_youtube(hashtags: list, api_key: str) -> list:
    """Mengecek seberapa populer hashtag spesifik langsung ke pencarian YouTube."""
    results = []
    for ht in hashtags:
        clean_ht = ht.replace("#", "")
        print(f"[+] Memverifikasi tren hashtag: #{clean_ht}...")
        params = {
            "part": "snippet",
            "q": f"#{clean_ht}",
            "type": "video",
            "maxResults": 5,
            "key": api_key
        }
        res = call_youtube_api("search", params)
        total_results = res.get("pageInfo", {}).get("totalResults", 0)
        results.append({"hashtag": f"#{clean_ht}", "estimated_reach_score": total_results})
        time.sleep(0.5)  # Jeda aman penanganan kuota
    return results


# ---------------------------------------------------------------------------
# 4) MAIN ENTRYPOINT & CSV EXPORTER
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="YouTube Keyword & Hashtag Finder")
    parser.add_argument("--keywords", nargs="+", help="Satu atau lebih keyword target untuk diriset")
    parser.add_argument("--verify-hashtags", nargs="+", help="Daftar hashtag langsung untuk diverifikasi performanya")
    parser.add_argument("--api-key", help="YouTube Data API v3 Key (Opsional untuk sekadar autocomplete gratis)")
    
    args = parser.parse_args()
    
    # Ambil API key dari parameter atau dari Environment Variables github/sistem
    api_key = args.api_key or os.environ.get("YT_API_KEY")
    
    # Memastikan folder results/ selalu ada sebelum menulis file CSV
    os.makedirs("results", exist_ok=True)
    
    if not args.keywords and not args.verify_hashtags:
        parser.print_help()
        sys.exit("\nError: Anda harus memasukkan parameter --keywords atau --verify-hashtags!")

    # JALUR A: Mode Verifikasi Hashtag Langsung
    if args.verify_hashtags:
        if not api_key:
            sys.exit("Error: Fitur --verify-hashtags membutuhkan parameter --api-key!")
        
        verified_data = verify_hashtags_on_youtube(args.verify_hashtags, api_key)
        
        csv_file = "results/verified_hashtags_report.csv"
        with open(csv_file, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["hashtag", "estimated_reach_score"])
            writer.writeheader()
            writer.writerows(verified_data)
        print(f"\n[✓] Selesai! Laporan verifikasi hashtag disimpan ke: {csv_file}")
        return

    # JALUR B: Mode Riset Kata Kunci Utama
    if args.keywords:
        all_suggestions = set()
        
        # 1. Tarik Google Autocomplete (Fitur Gratis)
        print("[*] Tahap 1: Mengambil Autocomplete Suggestions Gratis...")
        for kw in args.keywords:
            suggestions = get_autocomplete_suggestions(kw)
            for s in suggestions:
                all_suggestions.add(s)
        
        print(f"[✓] Berhasil menemukan {len(all_suggestions)} variasi keyword turunan.")
        
        # 2. Jika API Key Disediakan, Lakukan Deep Analysis Kompetitor
        extracted_tags = []
        extracted_hashtags = []
        
        if api_key:
            print("\n[*] Tahap 2: Menghubungkan ke YouTube API untuk Analisis Video Kompetitor...")
            for kw in args.keywords:
                v_ids = get_top_videos_by_keyword(kw, api_key, max_results=7)
                v_details = get_video_details(v_ids, api_key)
                
                for detail in v_details:
                    extracted_tags.extend(detail["tags"])
                    extracted_hashtags.extend(detail["hashtags"])
            
            # Hitung frekuensi tag & hashtag terbanyak
            top_tags = [item[0] for item in Counter(extracted_tags).most_common(20)]
            top_hashtags = [f"#{item[0]}" for item in Counter(extracted_hashtags).most_common(20)]
        else:
            print("\n[!] Petunjuk: Masukkan --api-key untuk mengekstrak tag & hashtag dari video top kompetitor.")
            top_tags = ["Butuh API Key"]
            top_hashtags = ["Butuh API Key"]

        # 3. Export Hasil Gabungan Akhir ke CSV di Folder results/
        csv_file = "results/youtube_research_results.csv"
        with open(csv_file, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Type", "Value"])
            
            for kw_suggest in sorted(list(all_suggestions)):
                writer.writerow(["Keyword Suggestion", kw_suggest])
            for tag in top_tags:
                writer.writerow(["Top Competitor Tag", tag])
            for ht in top_hashtags:
