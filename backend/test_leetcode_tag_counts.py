import requests
import json
import sys

username = sys.argv[1] if len(sys.argv) > 1 else "lee215"

QUERY = """
query skillStats($username: String!) {
    matchedUser(username: $username) {
        username
        submitStats {
            acSubmissionNum {
                difficulty
                count
            }
        }
        tagProblemCounts {
            advanced {
                tagName
                tagSlug
                problemsSolved
            }
            intermediate {
                tagName
                tagSlug
                problemsSolved
            }
            fundamental {
                tagName
                tagSlug
                problemsSolved
            }
        }
    }
}
"""

response = requests.post(
    "https://leetcode.com/graphql",
    json={
        "query": QUERY,
        "variables": {"username": username},
    },
    headers={
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com/",
        "User-Agent": "Mozilla/5.0",
    },
    timeout=20,
)

print("HTTP:", response.status_code)

data = response.json()

print(json.dumps(data, indent=2))