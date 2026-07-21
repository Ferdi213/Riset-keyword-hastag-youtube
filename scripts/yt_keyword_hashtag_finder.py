#!/usr/bin/env python3
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
from datetime import datetime, timedelta, timezone

HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)

def get_autocomplete_suggestions(seed_keyword: str, hl: str = "id", gl: str = "ID") -> list:
    params = {"client": "firefox", "ds": "yt", "q": seed_keyword, "hl": hl, "gl": gl}
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data[1] if len(data) > 1 else []
    except Exception as e:
        print(f"  [!] Gagal ambil suggestion untuk '{seed_keyword}': {e}", file=sys.stderr)
        return []

def youtube_api_get(endpoint: str, params: dict, api_key: str) -> dict:
    params["key"] = api_key
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def search_top_videos(keyword: str, api_key: str, max_results: int = 15, region_code: str = "ID") -> list:
    params = {
        "part": "snippet", "q": keyword, "type": "video", "order": "viewCount",
        "maxResults": min(max_results, 50), "regionCode": region_code
    }
    try:
        data = youtube_api_get("search", params, api_key)
    except Exception as e:
        print(f"  [!] Search API error untuk '{keyword}': {e}", file=sys.stderr)
        return []
    return [item["id"]["videoId"] for item in data.get("items", []) if "videoId" in item.get("id", {})]

def get_video_details(video_ids: list, api_key: str) -> list:
    if not video_ids: return []
    details = []
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
                "video_id": item.get("id"), "title": snippet.get("title", ""),
                "description": snippet.get("description", ""), "tags": snippet.get("tags", []),
                "view_count": int(stats.get("viewCount", 0)), "channel": snippet.get("channelTitle", ""),
            })
    return details

def extract_hashtags(text: str) -> list:
    return [f"#{tag}" for tag in HASHTAG_RE.findall(text)]

def analyze_keyword(keyword: str, api_key: str, max_results: int = 15) -> dict:
    print(f"[*] Menganalisis video top untuk: '{keyword}'")
    video_ids = search_top_videos(keyword, api_key, max_results=max_results)
    details = get_video_details(video_ids, api_key)
    hashtag_views = {}
    tag_counter = Counter()
    for v in details:
        seen = set(h.lower() for h in extract_hashtags(v["title"] + " " + v["description"]))
        for h in seen:
            hashtag_views.setdefault(h, []).append(v["view_count"])
        for t in v["tags"]:
            tag_counter[t.lower()] += 1
    hashtag_stats = []
    for tag, views_list in hashtag_views.items():
        hashtag_stats.append({
            "hashtag": tag, "video_count": len(views_list),
            "avg_views": round(sum(views_list) / len(views_list)),
            "total_views": sum(views_list), "max_views": max(views_list),
        })
    hashtag_stats.sort(key=lambda x: -x["total_views"])
    return {"hashtag_stats": hashtag_stats}

def verify_specific_hashtags(hashtags: list, api_key: str) -> list:
    results = []
    for ht in hashtags:
        clean_ht = ht.replace("#", "")
        print(f"[*] Memverifikasi hashtag: #{clean_ht}")
        try:
            data = youtube_api_get("search", {"part": "snippet", "q": f"#{clean_ht}", "type": "video", "maxResults": 5}, api_key)
            results.append({"hashtag": f"#{clean_ht}", "estimated_reach_score": data.get("pageInfo", {}).get("totalResults", 0)})
        except Exception as e:
            print(f"  [!] Gagal: {e}", file=sys.stderr)
        time.sleep(0.2)
    return results

def main():
    parser = argparse.ArgumentParser(description="YouTube Keyword & Hashtag Finder")
    parser.add_argument("--keywords", nargs="+")
    parser.add_argument("--api-key")
    parser.add_argument("--keywords-file")
    parser.add_argument("--max-videos", type=int, default=15)
    parser.add_argument("--csv")
    parser.add_argument("--verify-hashtags-file")
    parser.add_argument("--suggest-from-file") # Fitur baru
    
    args = parser.parse_args()
    api_key = args.api_key or os.environ.get("YT_API_KEY")

    os.makedirs("results", exist_ok=True)

    # 1. Fitur Autocomplete
    if args.suggest_from_file and os.path.exists(args.suggest_from_file):
        with open(args.suggest_from_file, "r", encoding="utf-8") as f:
            seeds = [line.strip() for line in f if line.strip()]
        all_suggestions = []
        for seed in seeds:
            print(f"[*] Mencari saran pencarian untuk: '{seed}'")
            all_suggestions.extend(get_autocomplete_suggestions(seed))
        
        with open("results/autocomplete_suggestions.txt", "w", encoding="utf-8") as f:
            for item in sorted(set(all_suggestions)):
                f.write(f"{item}\n")
        print("[✓] Saran pencarian disimpan ke: results/autocomplete_suggestions.txt")

    # 2. Proses Keyword (Analisis Hashtag)
    target_keywords = args.keywords or []
    if args.keywords_file and os.path.exists(args.keywords_file):
        with open(args.keywords_file, "r", encoding="utf-8") as f:
            target_keywords += [line.strip() for line in f if line.strip()]

    if target_keywords and api_key:
        for kw in target_keywords:
            data = analyze_keyword(kw, api_key, max_results=args.max_videos)
            output_file = args.csv if args.csv else f"results/analysis_{kw.replace(' ', '_')}.csv"
            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["hashtag", "video_count", "avg_views", "total_views", "max_views"])
                writer.writeheader()
                writer.writerows(data["hashtag_stats"])
            print(f"[✓] Hasil keyword disimpan ke: {output_file}")

    # 3. Proses Hashtag Verifikasi
    if args.verify_hashtags_file and os.path.exists(args.verify_hashtags_file) and api_key:
        with open(args.verify_hashtags_file, "r", encoding="utf-8") as f:
            target_hashtags = [line.strip() for line in f if line.strip()]
        verified = verify_specific_hashtags(target_hashtags, api_key)
        with open("results/verified_hashtags.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["hashtag", "estimated_reach_score"])
            writer.writeheader()
            writer.writerows(verified)
        print("[✓] Hasil verifikasi hashtag disimpan ke: results/verified_hashtags.csv")

if __name__ == "__main__":
    main()
