"""
Live integration test: POST /sync/codeforces/2
Uses the dev user's JWT stored in codepulse.access_token
(if available in local storage) OR reads it from a temp env var.

Run:
    CODEPULSE_TOKEN=<token> ..\.venv\Scripts\python scripts\test_live_sync.py

IMPORTANT: Do NOT log or expose the token itself.
"""

import os
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"
PROFILE_ID = 2

token = os.environ.get("CODEPULSE_TOKEN", "").strip()
if not token:
    print("ERROR: Set CODEPULSE_TOKEN=<your_jwt> before running this script.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
}

print("=" * 60)
print(f"CodePulse Live Sync Test  →  POST /sync/codeforces/{PROFILE_ID}")
print("=" * 60)
print(f"\n  Backend : {BASE_URL}")
print(f"  Profile : {PROFILE_ID}")
print(f"  Token   : ***{token[-6:]}  (last 6 chars only)")

print("\n[Step 1] Verify platform profile exists...")
try:
    r = httpx.get(f"{BASE_URL}/platform-profiles/me", headers=headers, timeout=10)
    print(f"  GET /platform-profiles/me → {r.status_code}")
    profiles = r.json()
    cf = next((p for p in profiles if p.get("platform") == "codeforces"), None)
    if cf:
        print(f"  Found Codeforces profile: id={cf['id']}  username={cf['username']}")
    else:
        print("  WARNING: No Codeforces profile found in /me response.")
except Exception as e:
    print(f"  ERROR: {e}")

print(f"\n[Step 2] POST /sync/codeforces/{PROFILE_ID} ...")
t0 = time.perf_counter()
try:
    r = httpx.post(
        f"{BASE_URL}/sync/codeforces/{PROFILE_ID}",
        headers=headers,
        timeout=120.0,  # sync can take up to ~60s for large histories
    )
    elapsed = time.perf_counter() - t0
    print(f"  HTTP {r.status_code}  ({elapsed:.1f}s)")

    if r.status_code == 200:
        result = r.json()
        print("  SUCCESS ✓")
        print(f"  problems_created          : {result.get('problems_created')}")
        print(f"  contests_created          : {result.get('contests_created')}")
        print(f"  submissions_created       : {result.get('submissions_created')}")
        print(f"  submissions_skipped       : {result.get('submissions_skipped')}")
        print(f"  rating_history_created    : {result.get('rating_history_created')}")
        print(f"  participations_created    : {result.get('contest_participations_created')}")
        print(f"  problems_solved           : {result.get('problems_solved')}")
        print(f"  contests_attended         : {result.get('contests_attended')}")
        print(f"  synced_at                 : {result.get('synced_at')}")
    else:
        body = r.text
        print(f"  FAILED: {body}")

except httpx.TimeoutException as e:
    elapsed = time.perf_counter() - t0
    print(f"  TIMEOUT after {elapsed:.1f}s: {e}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n[Step 3] Second sync (idempotency check) ...")
t0 = time.perf_counter()
try:
    r = httpx.post(
        f"{BASE_URL}/sync/codeforces/{PROFILE_ID}",
        headers=headers,
        timeout=120.0,
    )
    elapsed = time.perf_counter() - t0
    print(f"  HTTP {r.status_code}  ({elapsed:.1f}s)")
    if r.status_code == 200:
        result = r.json()
        submissions_created_2nd = result.get("submissions_created", -1)
        print(f"  submissions_created (2nd sync): {submissions_created_2nd}")
        if submissions_created_2nd == 0:
            print("  Idempotent ✓  (no duplicate submissions inserted)")
        else:
            print(f"  WARNING: {submissions_created_2nd} new submissions created on second sync.")
    else:
        print(f"  FAILED: {r.text}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("Live sync test complete.")
print("=" * 60)
