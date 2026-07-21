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
    return [item["id"]["videoId"] for item in data.get("items", []) if "videoId" in item.get("id", {})]


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
    Buat tiap hashtag yang ditemukan, hitung juga rata-rata & total views
    dari video-video yang memakainya — jadi langsung ketahuan hashtag mana
    yang dipakai video RAME vs yang dipakai video sepi, tanpa perlu nebak
    daftar hashtag duluan.
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
        "top_hidden_tags": tag_counter.most_common(15),
        "top_videos": sorted(details, key=lambda x: -x["view_count"])[:5],
    }


# ---------------------------------------------------------------------------
# 3) VERIFIKASI HASHTAG REAL — cek apakah hashtag beneran dipakai di video
#    nyata di YouTube, dan seberapa rame (jumlah video + total/avg views).
#    Ini yang jawab pertanyaan "hashtag ini beneran ada/rame di YouTube ga".
# ---------------------------------------------------------------------------
def verify_hashtag(hashtag: str, api_key: str, sample_size: int = 25) -> dict:
    """
    Search YouTube pakai hashtag sebagai query (persis kayak orang search
    manual di kolom search), lalu ambil statistik video-video yang muncul.
    Ini bukti langsung dari data YouTube, bukan tebakan dari artikel SEO.
    """
    tag = hashtag.lstrip("#").strip()
    query = f"#{tag}"
    print(f"[*] Verifikasi hashtag: {query}")

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "viewCount",
        "maxResults": sample_size,
    }
    try:
        search_data = youtube_api_get("search", params, api_key)
    except Exception as e:
        print(f"  [!] Gagal cek '{query}': {e}", file=sys.stderr)
        return {"hashtag": query, "exists": False, "error": str(e)}

    total_results = search_data.get("pageInfo", {}).get("totalResults", 0)
    video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])
                 if "videoId" in item.get("id", {})]

    if not video_ids:
        return {
            "hashtag": query,
            "exists": False,
            "total_results_estimate": total_results,
            "sample_size": 0,
            "avg_views": 0,
            "max_views": 0,
            "verdict": "TIDAK DITEMUKAN — tidak ada video yang benar-benar pakai hashtag ini",
        }

    details = get_video_details(video_ids, api_key)
    # cuma hitung video yang BENERAN menyertakan hashtag itu di title/description
    # (search YouTube kadang loose-match, jadi kita filter ketat di sini)
    genuine = [v for v in details if f"#{tag.lower()}" in (v["title"] + v["description"]).lower()]

    views = [v["view_count"] for v in genuine] if genuine else [v["view_count"] for v in details]
    avg_views = round(sum(views) / len(views)) if views else 0
    max_views = max(views) if views else 0

    # klasifikasi kasar seberapa "rame"
    if avg_views >= 100_000:
        verdict = "RAME — rata-rata views tinggi, kompetisi kemungkinan ketat"
    elif avg_views >= 10_000:
        verdict = "CUKUP RAME — volume sedang, peluang masih terbuka"
    elif avg_views >= 1_000:
        verdict = "SEPI-SEDANG — kompetisi rendah, cocok buat channel kecil"
    else:
        verdict = "SANGAT SEPI — hati-hati, bisa jadi hashtag ini jarang dicari"

    return {
        "hashtag": query,
        "exists": True,
        "genuine_matches": len(genuine),
        "total_results_estimate": total_results,
        "sample_size": len(details),
        "avg_views": avg_views,
        "max_views": max_views,
        "top_video_title": max(details, key=lambda x: x["view_count"])["title"] if details else "",
        "verdict": verdict,
    }


def verify_hashtags(hashtags: list, api_key: str) -> list:
    results = []
    for h in hashtags:
        results.append(verify_hashtag(h, api_key))
        time.sleep(0.2)
    return results


def print_verification_report(results: list):
    print("\n=== HASIL VERIFIKASI HASHTAG (data real dari YouTube) ===\n")
    # urutkan dari yang paling rame
    results_sorted = sorted(results, key=lambda r: r.get("avg_views", 0), reverse=True)
    for r in results_sorted:
        print(f"{r['hashtag']}")
        if not r.get("exists"):
            print(f"   -> {r.get('verdict', 'TIDAK DITEMUKAN')}")
            print()
            continue
        print(f"   Estimasi total video terkait : {r['total_results_estimate']:,}")
        print(f"   Video yang genuinely pakai tag di sample: {r['genuine_matches']}/{r['sample_size']}")
        print(f"   Rata-rata views (sample)     : {r['avg_views']:,}")
        print(f"   Views tertinggi (sample)     : {r['max_views']:,}")
        print(f"   Video top pakai tag ini      : {r['top_video_title']}")
        print(f"   Verdict                      : {r['verdict']}")
        print()


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------
def print_keyword_report(suggestions: list):
    print("\n=== HASIL RISET KEYWORD (autocomplete) ===")
    if not suggestions:
        print("Tidak ada suggestion ditemukan.")
        return
    for i, kw in enumerate(suggestions, 1):
        print(f"{i:>3}. {kw}")


def print_hashtag_report(results: list):
    print("\n=== HASHTAG YANG DIPAKAI VIDEO TOP (otomatis ditemukan dari keyword) ===")
    for r in results:
        print(f"\n--- Keyword: '{r['keyword']}' "
              f"(sample {r['video_sample_size']} video, avg views {r['avg_views']:,}) ---")
        print("Hashtag ditemukan, diurutkan dari yang paling rame:")
        if r["hashtag_stats"]:
            print(f"   {'HASHTAG':<25}{'DIPAKAI DI':<14}{'AVG VIEWS':<15}{'TOTAL VIEWS':<15}")
            for h in r["hashtag_stats"]:
                print(f"   #{h['hashtag']:<24}{h['video_count']} video{'':<7}"
                      f"{h['avg_views']:>10,}   {h['total_views']:>12,}")
        else:
            print("   (tidak ada hashtag terdeteksi di judul/deskripsi video top untuk keyword ini)")

        print("\nTag tersembunyi (metadata) yang paling sering dipakai:")
        if r["top_hidden_tags"]:
            for tag, count in r["top_hidden_tags"][:10]:
                print(f"   {tag}   ({count}x)")
        else:
            print("   (tidak ada tag metadata terdeteksi)")

        print("\nVideo top performer buat referensi:")
        for v in r["top_videos"]:
            print(f"   [{v['view_count']:,} views] {v['title']}  —  {v['channel']}")


def save_csv(results: list, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["keyword", "type", "value", "video_count_or_views", "avg_views", "total_views"])
        for r in results:
            for h in r["hashtag_stats"]:
                writer.writerow([r["keyword"], "hashtag", f"#{h['hashtag']}",
                                  h["video_count"], h["avg_views"], h["total_views"]])
            for tag, count in r["top_hidden_tags"]:
                writer.writerow([r["keyword"], "hidden_tag", tag, count, "", ""])
            for v in r["top_videos"]:
                writer.writerow([r["keyword"], "top_video", v["title"], v["view_count"], "", ""])
    print(f"\n[+] Hasil disimpan ke: {path}")


def save_verification_csv(results: list, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hashtag", "exists", "avg_views", "max_views",
                          "total_results_estimate", "genuine_matches", "sample_size", "verdict"])
        for r in results:
            writer.writerow([
                r.get("hashtag"), r.get("exists"), r.get("avg_views", 0), r.get("max_views", 0),
                r.get("total_results_estimate", 0), r.get("genuine_matches", 0),
                r.get("sample_size", 0), r.get("verdict", ""),
            ])
    print(f"\n[+] Hasil verifikasi disimpan ke: {path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def read_list_file(path: str) -> list:
    """Baca file txt, satu item per baris. Baris kosong & yang diawali # (komentar) diabaikan."""
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
    return items


def main():
    parser = argparse.ArgumentParser(description="YouTube Keyword & Hashtag Finder")
    parser.add_argument("--keywords", nargs="+", default=None,
                         help="Satu atau lebih seed keyword, mis: --keywords \"resep ayam\" \"tutorial excel\"")
    parser.add_argument("--keywords-file", default=None,
                         help="Path file txt berisi satu keyword per baris (buat dipakai di GitHub Actions)")
    parser.add_argument("--verify-hashtags", nargs="+", default=None,
                         help="Cek satu-satu apakah hashtag ini beneran ada & rame di YouTube, "
                              "mis: --verify-hashtags github githubpages webdev (butuh --api-key)")
    parser.add_argument("--verify-hashtags-file", default=None,
                         help="Path file txt berisi satu hashtag per baris (buat dipakai di GitHub Actions)")
    parser.add_argument("--api-key", default=os.environ.get("YT_API_KEY"),
                         help="YouTube Data API v3 key (opsional, tapi wajib buat analisis hashtag/video)")
    parser.add_argument("--deep", action="store_true",
                         help="Perluas pencarian suggestion pakai a-z (lebih banyak hasil, lebih lambat)")
    parser.add_argument("--max-videos", type=int, default=25,
                         help="Jumlah video top yang dianalisis per keyword (default 25)")
    parser.add_argument("--csv", default=None,
                         help="Path file CSV buat simpan hasil analisis hashtag (butuh --api-key)")
    args = parser.parse_args()

    # Gabungkan input dari CLI dan dari file (kalau ada)
    keywords = list(args.keywords) if args.keywords else []
    if args.keywords_file:
        keywords += read_list_file(args.keywords_file)
    keywords = sorted(set(keywords)) if keywords else None

    hashtags = list(args.verify_hashtags) if args.verify_hashtags else []
    if args.verify_hashtags_file:
        hashtags += read_list_file(args.verify_hashtags_file)
    hashtags = sorted(set(hashtags)) if hashtags else None

    if not keywords and not hashtags:
        parser.error("Isi minimal salah satu: --keywords/--keywords-file ATAU --verify-hashtags/--verify-hashtags-file")

    # Mode verifikasi hashtag (butuh API key, wajib)
    if hashtags:
        if not args.api_key:
            parser.error("--verify-hashtags butuh --api-key (lihat docstring di atas cara dapetinnya, gratis)")
        v_results = verify_hashtags(hashtags, args.api_key)
        print_verification_report(v_results)
        if args.csv:
            save_verification_csv(v_results, args.csv)

    if not keywords:
        return

    # Tahap 1: keyword suggestion (selalu jalan, gratis)
    suggestions = expand_keywords(keywords, deep=args.deep)
    print_keyword_report(suggestions)

    # Tahap 2: analisis hashtag & video top (kalau ada API key)
    if args.api_key:
        results = [analyze_keyword(kw, args.api_key, args.max_videos) for kw in keywords]
        print_hashtag_report(results)
        if args.csv:
            save_csv(results, args.csv)
    else:
        print("\n[i] Mau lihat hashtag & video yang lagi trending juga? "
              "Tambahin --api-key YOUR_KEY (lihat docstring di atas cara dapetinnya, gratis).")


if __name__ == "__main__":
    main()
