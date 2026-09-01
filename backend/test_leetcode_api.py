import sys
import httpx
import json

print("=== DEEP DIVE: NOWORNEVEREV/LEETCODE-API WITH TOPIC TAGS ===\n")

working_username = 'lee215'

# The key finding: noworneverev/leetcode-api returns submissions with topicTags
print("1. Deep dive into noworneverev/leetcode-api submissions with topicTags:")

try:
    endpoint = f"https://leetcode-api-pied.vercel.app/user/{working_username}/submissions"
    response = httpx.get(endpoint, timeout=10.0)
    data = response.json()
    
    print(f'   - Submissions count: {len(data)}')
    print(f'   - Sample submission with topicTags:')
    if data and len(data) > 0:
        sample = data[0]
        print(f'      {json.dumps(sample, indent=6)}')
        
        # Check if topicTags are actually populated
        has_topics = any(sub.get('topicTags') for sub in data)
        print(f'   - Submissions with topicTags: {sum(1 for sub in data if sub.get("topicTags"))}')
        
        # Try to get more submissions with different parameters
        print(f'\n2. Testing pagination with noworneverev/leetcode-api:')
        
        # Try with different endpoints/parameters
        paginated_endpoints = [
            f"https://leetcode-api-pied.vercel.app/user/{working_username}/submissions?limit=50",
            f"https://leetcode-api-pied.vercel.app/user/{working_username}/submissions?limit=100",
            f"https://leetcode-api-pied.vercel.app/user/{working_username}/submissions?limit=200",
        ]
        
        for endpoint in paginated_endpoints:
            print(f'\n   Testing {endpoint}:')
            try:
                response = httpx.get(endpoint, timeout=10.0)
                data = response.json()
                print(f'      - Submissions count: {len(data)}')
            except Exception as e:
                print(f'      - Exception: {str(e)}')
                
except Exception as e:
    print(f'Exception: {str(e)}')

# Test 3: Check if we can get all submissions via the API
print(f'\n3. Testing complete solved problem discovery via noworneverev/leetcode-api:')

try:
    # Check the API documentation or try different endpoints
    test_endpoints = [
        f"https://leetcode-api-pied.vercel.app/user/{working_username}/ac",
        f"https://leetcode-api-pied.vercel.app/user/{working_username}/accepted",
        f"https://leetcode-api-pied.vercel.app/user/{working_username}/solved",
        f"https://leetcode-api-pied.vercel.app/user/{working_username}/problems",
    ]
    
    for endpoint in test_endpoints:
        print(f'\n   Testing {endpoint}:')
        try:
            response = httpx.get(endpoint, timeout=10.0)
            print(f'      - Status: {response.status_code}')
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f'      - Response type: JSON')
                    if isinstance(data, dict):
                        print(f'      - Keys: {data.keys()}')
                    elif isinstance(data, list):
                        print(f'      - List length: {len(data)}')
                        if data:
                            print(f'      - Sample: {data[0]}')
                except:
                    print(f'      - Non-JSON response')
        except Exception as e:
            print(f'      - Exception: {str(e)}')

except Exception as e:
    print(f'Exception: {str(e)}')

print("\n=== INVESTIGATION COMPLETE ===")