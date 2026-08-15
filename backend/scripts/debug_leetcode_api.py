"""
Debug script to test LeetCode GraphQL API directly.
"""

import httpx
import json

GRAPHQL_URL = "https://leetcode.com/graphql"

def test_simple_query(username="leetcode"):
    """Test a simple GraphQL query to LeetCode API."""
    
    # Try the simplest possible query first
    query = """
    query getUserProfile($username: String!) {
        matchedUser(username: $username) {
            username
        }
    }
    """
    
    payload = {
        "query": query,
        "variables": {"username": username}
    }
    
    print(f"Testing LeetCode GraphQL API with username: {username}")
    print("=" * 60)
    print(f"Endpoint: {GRAPHQL_URL}")
    print(f"Query: {query.strip()}")
    print(f"Variables: {payload['variables']}")
    print("=" * 60)
    
    try:
        response = httpx.post(
            GRAPHQL_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Referer": "https://leetcode.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=10.0,
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"\nResponse Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"].get("matchedUser"):
                print(f"\n✅ Success! Found user: {data['data']['matchedUser']['username']}")
                return True
            elif "errors" in data:
                print(f"\n❌ GraphQL Errors: {data['errors']}")
                return False
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    username = sys.argv[1] if len(sys.argv) > 1 else "leetcode"
    success = test_simple_query(username)
    sys.exit(0 if success else 1)
