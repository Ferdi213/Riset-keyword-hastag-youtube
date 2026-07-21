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

def expand_keywords(seed_keywords: list, deep: bool = False) -> list:
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
                time.sleep(0.15)
    return sorted(all_suggestions)

def youtube_api_get(endpoint: str, params: dict, api_key: str) -> dict:
    params["key"] = api_key
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def search_top_videos(keyword: str, api_key: str, max_results: int = 15,
                       region_code: str = "ID", published_within_days: int = 90) -> list:
    published_after = (datetime.now(timezone.utc) - timedelta(days=published_within_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "part": "snippet", "q": keyword, "type": "video", "order": "viewCount",
        "maxResults": min(max_results, 50), "regionCode": region_code, "publishedAfter": published_after,
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

def analyze_keyword(keyword: str, api_key: str, max_results: int = 25) -> dict:
    print(f"[*] Menganalisis video top untuk: '{keyword}'")
    video_ids = search_top_videos(keyword, api_key, max_results=max_results)
    details = get_video_details(video_ids, api_key)
    hashtag_views = {}
    tag_counter = Counter()
    total_views = 0
    for v in details:
        total_views += v["view_count"]
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
    return {
        "keyword": keyword, "video_sample_size": len(details),
        "avg_views": round(total_views / len(details)) if details else 0,
        "hashtag_stats": hashtag_stats, "top_hidden_tags": tag_counter.most_common(20)
    }

def verify_specific_hashtags(hashtags: list, api_key: str) -> list:
    results = []
    for ht in hashtags:
        clean_ht = ht.replace("#", "")
        print(f"[*] Memverifikasi performa tren hashtag: #{clean_ht}")
        try:
            data = youtube_api_get("search", {"part": "snippet", "q": f"#{clean_ht}", "type": "video", "maxResults": 5}, api_key)
            results.append({"hashtag": f"#{clean_ht}", "estimated_reach_score": data.get("pageInfo", {}).get("totalResults", 0)})
        except Exception as e:
            print(f"  [!] Gagal memverifikasi hashtag #{clean_ht}: {e}", file=sys.stderr)
        time.sleep(0.2)
    return results

def read_lines_from_file(filepath: str) -> list:
    if not os.path.exists(filepath): return []
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

    file_keywords = read_lines_from_file("config/keywords.txt")
    file_hashtags = read_lines_from_file("config/hashtags.txt")

    target_keywords = (args.keywords or []) + file_keywords
    target_hashtags = (args.verify_hashtags or []) + file_hashtags

    os.makedirs("results", exist_ok=True)
    if not target_keywords and not target_hashtags:
        print("[!] Tidak ada kata kunci atau hashtag ditemukan. Berjalan dalam mode demo...")
        target_keywords = ["resep masakan"]

    if target_keywords:
        print("\n=== MEMULAI RISET KEYWORD ===")
        expanded = expand_keywords(target_keywords, deep=args.deep)
        with open("results/keyword_suggestions.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword Suggestion"])
            for kw in expanded: writer.writerow([kw])
        
        if api_key:
            for kw in target_keywords:
                analysis = analyze_keyword(kw, api_key)
                with open(f"results/analysis_hashtags_{kw.replace(' ', '_')}.csv", "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["hashtag", "video_count", "avg_views", "total_views", "max_views"])
                    writer.writeheader(); writer.writerows(analysis["hashtag_stats"])

    if target_hashtags:
        if not api_key: print("\n[!] Butuh API Key untuk verifikasi.")
        else:
            verified = verify_specific_hashtags(target_hashtags, api_key)
            with open("results/verified_hashtags.csv", "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["hashtag", "estimated_reach_score"])
                writer.writeheader(); writer.writerows(verified)

if __name__ == "__main__":
    main()

