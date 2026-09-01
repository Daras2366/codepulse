import requests
import json

QUERY = """
query {
    __schema {
        queryType {
            fields {
                name
            }
        }
    }
}
"""

response = requests.post(
    "https://leetcode.com/graphql",
    json={"query": QUERY},
    headers={
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com/",
        "User-Agent": "Mozilla/5.0",
    },
    timeout=20,
)

print("HTTP:", response.status_code)
print(json.dumps(response.json(), indent=2))