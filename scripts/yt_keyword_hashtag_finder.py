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
