import requests

URL = "https://leetcode.com/graphql"

QUERY = """
query getProblems(
    $categorySlug: String
    $limit: Int
    $skip: Int
    $filters: QuestionListFilterInput
) {
    questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
    ) {
        totalNum
        data {
            questionFrontendId
            title
            titleSlug
            difficulty
            status
            topicTags {
                name
                id
                slug
            }
        }
    }
}
"""

variables = {
    "categorySlug": "",
    "limit": 100,
    "skip": 0,
    "filters": {},
}

response = requests.post(
    URL,
    json={
        "query": QUERY,
        "variables": variables,
    },
    headers={
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com/problemset/",
        "User-Agent": "Mozilla/5.0",
    },
)

print("HTTP:", response.status_code)

data = response.json()

if "errors" in data:
    print("ERRORS:")
    print(data["errors"])
    raise SystemExit(1)

result = data["data"]["questionList"]

print("TOTAL:", result["totalNum"])
print("RETURNED:", len(result["data"]))

for problem in result["data"][:10]:
    print()
    print(problem["questionFrontendId"], problem["title"])
    print("slug:", problem["titleSlug"])
    print("difficulty:", problem["difficulty"])
    print("status:", problem["status"])
    print(
        "topics:",
        [tag["name"] for tag in problem["topicTags"]]
    )
    
all_problems = []

skip = 0
limit = 100

while True:
    variables["skip"] = skip

    response = requests.post(
        URL,
        json={
            "query": QUERY,
            "variables": variables,
        },
        headers={
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com/problemset/",
            "User-Agent": "Mozilla/5.0",
        },
    )

    data = response.json()["data"]["questionList"]

    problems = data["data"]

    all_problems.extend(problems)

    print(
        f"Fetched {len(all_problems)} / {data['totalNum']}"
    )

    if len(all_problems) >= data["totalNum"]:
        break

    skip += limit

print()
print("TOTAL PROBLEMS:", len(all_problems))

with_topics = [
    p for p in all_problems
    if p["topicTags"]
]

print("WITH TOPICS:", len(with_topics))