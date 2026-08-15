"""Test individual LeetCode GraphQL fields to find which ones work."""

import httpx
import json

GRAPHQL_URL = "https://leetcode.com/graphql"
username = "leetcode"

def test_query(name, query):
    """Test a specific query."""
    print(f"\nTesting: {name}")
    print("-" * 40)
    
    payload = {
        "query": query,
        "variables": {"username": username}
    }
    
    try:
        response = httpx.post(
            GRAPHQL_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Referer": "https://leetcode.com",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=10.0,
        )
        
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print(f"❌ GraphQL Error: {data['errors'][0]['message']}")
                return False
            else:
                print(f"✅ Success!")
                print(json.dumps(data, indent=2)[:500])
                return True
        else:
            print(f"❌ HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

# Test 1: Just username
test_query("Basic username", """
query ($username: String!) {
    matchedUser(username: $username) {
        username
    }
}
""")

# Test 2: Profile with ranking
test_query("Profile with ranking", """
query ($username: String!) {
    matchedUser(username: $username) {
        username
        profile {
            ranking
        }
    }
}
""")

# Test 3: Submit stats
test_query("Submit stats", """
query ($username: String!) {
    matchedUser(username: $username) {
        username
        submitStats {
            acSubmissionNum {
                difficulty
                count
            }
        }
    }
}
""")

# Test 4: Contest ranking
test_query("Contest ranking", """
query ($username: String!) {
    matchedUser(username: $username) {
        username
        userContestRanking {
            rating
            globalRanking
        }
    }
}
""")

# Test 5: Full profile (current implementation)
test_query("Full profile", """
query ($username: String!) {
    matchedUser(username: $username) {
        username
        profile {
            ranking
        }
        submitStats {
            acSubmissionNum {
                difficulty
                count
            }
        }
        userContestRanking {
            rating
            globalRanking
            attendedContestsCount
        }
    }
}
""")
