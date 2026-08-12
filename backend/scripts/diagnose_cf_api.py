"""
Diagnostic script: test each Codeforces API call made during sync in isolation.

Run from the backend directory:
    ..\.venv\Scripts\python scripts/diagnose_cf_api.py

IMPORTANT: Do NOT log credentials or JWTs.
"""

import sys
import time

import httpx

BASE_URL = "https://codeforces.com/api"
HANDLE = "jiangly"
TIMEOUT = 10.0  # same as CodeforcesClient default


def get(endpoint: str, params: dict | None = None, timeout: float = TIMEOUT) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    print(f"\n  GET {url}")
    print(f"  params  : {params}")
    print(f"  timeout : {timeout}s")
    t0 = time.perf_counter()
    try:
        resp = httpx.get(url, params=params, timeout=timeout)
        elapsed = time.perf_counter() - t0
        print(f"  HTTP    : {resp.status_code}  ({elapsed:.2f}s)")
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException as exc:
        elapsed = time.perf_counter() - t0
        print(f"  ERROR   : TIMEOUT after {elapsed:.2f}s — {exc}")
        return {}
    except httpx.HTTPStatusError as exc:
        elapsed = time.perf_counter() - t0
        print(f"  ERROR   : HTTP {exc.response.status_code} — {exc}")
        return {}
    except httpx.HTTPError as exc:
        elapsed = time.perf_counter() - t0
        print(f"  ERROR   : network error after {elapsed:.2f}s — {exc}")
        return {}
    except ValueError as exc:
        print(f"  ERROR   : JSON parse error — {exc}")
        return {}

    status = data.get("status")
    result = data.get("result")
    comment = data.get("comment", "")
    print(f"  status  : {status}")
    if status != "OK":
        print(f"  comment : {comment}")
        return {}

    if isinstance(result, list):
        print(f"  result  : list of {len(result)} items")
    elif isinstance(result, dict):
        keys = list(result.keys())[:6]
        print(f"  result  : dict keys={keys}")
    else:
        print(f"  result  : {type(result).__name__}")

    return data


def main():
    print("=" * 60)
    print("Codeforces API Diagnostic")
    print("=" * 60)

    print(f"\n[1] user.info  (handle={HANDLE})")
    d = get("user.info", {"handles": HANDLE})
    result = d.get("result", [])
    if result:
        u = result[0]
        print(f"  rating={u.get('rating')}  maxRating={u.get('maxRating')}  rank={u.get('rank')}")

    print(f"\n[2] user.status  (handle={HANDLE}, from=1, count=5)")
    d = get("user.status", {"handle": HANDLE, "from": 1, "count": 5})
    result = d.get("result", [])
    if result:
        print(f"  First submission id={result[0].get('id')}  verdict={result[0].get('verdict')}")

    print(f"\n[3] user.rating  (handle={HANDLE})")
    d = get("user.rating", {"handle": HANDLE})
    result = d.get("result", [])
    if result:
        last = result[-1]
        print(f"  Total rating events={len(result)}")
        print(f"  Last: contestId={last.get('contestId')}  newRating={last.get('newRating')}")

    print(f"\n[4] contest.list  (gym=false)")
    d = get("contest.list", {"gym": "false"})
    result = d.get("result", [])
    if result:
        print(f"  Total contests={len(result)}")

    print(f"\n[5] contest.list  (gym=true)  — note: this is a large payload")
    d = get("contest.list", {"gym": "true"})
    result = d.get("result", [])
    if result:
        print(f"  Total gym contests={len(result)}")

    print("\n" + "=" * 60)
    print("Diagnostic complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
