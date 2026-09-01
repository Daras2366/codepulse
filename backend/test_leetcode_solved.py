import requests
import json

URL = "https://leetcode.com/graphql"

QUERY = """
query userProgressQuestionList(
    $filters: UserProgressQuestionListInput
) {
    userProgressQuestionList(filters: $filters) {
        totalNum
        questions {
            frontendId
            title
            titleSlug
            difficulty
            lastSubmittedAt
            topicTags {
                name
                slug
            }
        }
    }
}
"""

variables = {
    "filters": {
        "questionStatus": "SOLVED",
        "skip": 0,
        "limit": 10,
    }
}

response = requests.post(
    URL,
    json={
        "query": QUERY,
        "variables": variables,
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