"""
Verify that OpenAPI endpoints are accessible.

This script checks:
1. GET /openapi.json returns valid JSON
2. GET /docs returns HTML with Swagger UI
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app

def verify_openapi_endpoints():
    """Verify OpenAPI endpoints work correctly."""
    
    client = TestClient(app)
    
    print("🔍 Verifying OpenAPI Endpoints")
    print("=" * 60)
    
    # Test /openapi.json
    print("\n1. Testing GET /openapi.json...")
    response = client.get("/openapi.json")
    
    if response.status_code == 200:
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Content-Type: {response.headers['content-type']}")
        
        data = response.json()
        print(f"   ✅ OpenAPI version: {data.get('openapi')}")
        print(f"   ✅ API title: {data.get('info', {}).get('title')}")
        print(f"   ✅ Total paths: {len(data.get('paths', {}))}")
        
        # Verify sync endpoints
        paths = data.get('paths', {})
        sync_paths = [p for p in paths if 'sync' in p]
        print(f"   ✅ Sync endpoints: {sync_paths}")
        
        # Verify Platform enum
        platform_schema = data.get('components', {}).get('schemas', {}).get('Platform')
        if platform_schema:
            print(f"   ✅ Platform enum values: {platform_schema.get('enum')}")
        else:
            print(f"   ⚠️  Platform enum not found in components/schemas")
    else:
        print(f"   ❌ Status: {response.status_code}")
        print(f"   ❌ Error: {response.text}")
        return False
    
    # Test /docs
    print("\n2. Testing GET /docs...")
    response = client.get("/docs")
    
    if response.status_code == 200:
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Content-Type: {response.headers['content-type']}")
        
        html = response.text
        if 'swagger' in html.lower():
            print(f"   ✅ Contains Swagger UI")
        else:
            print(f"   ⚠️  Swagger UI not detected in HTML")
    else:
        print(f"   ❌ Status: {response.status_code}")
        print(f"   ❌ Error: {response.text}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All OpenAPI endpoints working correctly!")
    return True


if __name__ == "__main__":
    import sys
    success = verify_openapi_endpoints()
    sys.exit(0 if success else 1)
