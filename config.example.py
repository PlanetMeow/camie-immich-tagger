# -*- coding: utf-8 -*-
"""
Copy this file to  config.py  and fill in your own values.
config.py is gitignored and must never be committed.
Secrets (API keys) are read from environment variables, so config.py holds no plaintext keys.
"""
import os

# ---- Paths ----
WORK_DIR  = r"D:\Software\ImageTagger"                    # where scripts + exiftool.exe + model live
EXIFTOOL  = os.path.join(WORK_DIR, "exiftool.exe")        # https://exiftool.org/  (Windows exe)
MODEL_DIR = os.path.join(WORK_DIR, "models", "camie-tagger-v2")
PIXAI_MODEL_DIR = os.path.join(WORK_DIR, "models", "pixai-tagger-v0.9")  # optional: character supplement (pixai_characters.py)

# Image library roots to scan (typically your immich External Library dirs)
SCAN_DIRS = [
    r"E:\YourLibrary\Folder1",
    r"E:\YourLibrary\Folder2",
]

# ---- immich ----
IMMICH_URL     = "http://127.0.0.1:2283"
IMMICH_API_KEY = os.environ.get("IMMICH_API_KEY", "")    # set env var, do NOT hardcode
LIBRARY_IDS    = [                                        # immich External Library UUIDs
    "your-immich-external-library-uuid-1",
    "your-immich-external-library-uuid-2",
]

# ---- SauceNAO (Tier 0 reverse search, optional) ----
SAUCENAO_API_KEY = os.environ.get("SAUCENAO_API_KEY", "") # set env var, do NOT hardcode
# Optional Tier 0 queue priority: (path regex, tier); first match wins, lower tier searched first,
# None = never search (e.g. artbook scans / AI images rarely hit). Empty = original queue order.
TIER0_PRIORITY = [
    # (r"^E:/YourLibrary/Folder1/(Artbooks|AI)/", None),
    # (r"^E:/YourLibrary/Folder1/", 1),
    # (r"^E:/YourLibrary/Folder2/Screenshots/", 3),
]

# ---- State files (usually leave as-is) ----
ERROR_LOG      = os.path.join(WORK_DIR, "camie_errors.txt")
DONE_LIST      = os.path.join(WORK_DIR, "camie_done.txt")
NO_CHAR_LIST   = os.path.join(WORK_DIR, "no_character_images.txt")
TIER0_PROGRESS = os.path.join(WORK_DIR, "tier0_progress.json")
TIER0_PENDING  = os.path.join(WORK_DIR, "tier0_danbooru_pending.json")  # SauceNAO hits awaiting Danbooru retry
DEL_LIST       = os.path.join(WORK_DIR, "tags_to_delete.txt")
KEEP_LIST      = os.path.join(WORK_DIR, "tags_keep.txt")
ORPHAN_LIST    = os.path.join(WORK_DIR, "orphan_sidecars.txt")
