"""
Tests for OpenAPI schema generation.

Ensures that FastAPI can generate the OpenAPI schema without errors,
particularly after adding new endpoints with enum path parameters.
"""

from unittest import TestCase


class OpenAPIGenerationTests(TestCase):
    """Test that OpenAPI schema generation works correctly."""

    def test_openapi_schema_generation_succeeds(self):
        """OpenAPI schema should be generated without Pydantic errors."""
        from app.main import app

        # This should not raise any Pydantic validation errors
        schema = app.openapi()

        # Verify schema structure
        self.assertIn("openapi", schema)
        self.assertIn("info", schema)
        self.assertIn("paths", schema)
        self.assertIn("components", schema)

        # Verify we have paths
        self.assertGreater(len(schema["paths"]), 0)

    def test_sync_endpoints_present_in_openapi(self):
        """Both sync endpoints should be present in OpenAPI schema."""
        from app.main import app

        schema = app.openapi()
        paths = schema["paths"]

        # Verify both sync endpoints exist
        self.assertIn("/sync/codeforces/{profile_id}", paths)
        self.assertIn("/sync/{platform}/{profile_id}", paths)

        # Verify they have POST methods
        self.assertIn("post", paths["/sync/codeforces/{profile_id}"])
        self.assertIn("post", paths["/sync/{platform}/{profile_id}"])

    def test_platform_parameter_is_enum_in_openapi(self):
        """Platform path parameter should be an enum in OpenAPI schema."""
        from app.main import app

        schema = app.openapi()
        generic_endpoint = schema["paths"]["/sync/{platform}/{profile_id}"]["post"]

        # Find the platform parameter
        platform_param = None
        for param in generic_endpoint["parameters"]:
            if param["name"] == "platform":
                platform_param = param
                break

        self.assertIsNotNone(platform_param, "Platform parameter not found")
        self.assertEqual(platform_param["in"], "path")
        self.assertTrue(platform_param["required"])

        # Platform should have a schema reference or enum values
        param_schema = platform_param.get("schema", {})
        
        # Check if it references the Platform enum in components/schemas
        if "$ref" in param_schema:
            # Extract the schema name from the reference
            ref = param_schema["$ref"]
            self.assertIn("Platform", ref)
            
            # Verify the Platform enum exists in components
            schema_name = ref.split("/")[-1]
            self.assertIn(schema_name, schema["components"]["schemas"])
            
            # Verify enum values
            platform_schema = schema["components"]["schemas"][schema_name]
            self.assertIn("enum", platform_schema)
            enum_values = platform_schema["enum"]
            self.assertIn("codeforces", enum_values)
            self.assertIn("leetcode", enum_values)
        else:
            # Inline enum definition
            self.assertIn("enum", param_schema)
            enum_values = param_schema["enum"]
            self.assertIn("codeforces", enum_values)
            self.assertIn("leetcode", enum_values)

    def test_sync_endpoints_return_sync_result(self):
        """Both sync endpoints should return SyncResult schema."""
        from app.main import app

        schema = app.openapi()
        paths = schema["paths"]

        # Check Codeforces endpoint
        cf_endpoint = paths["/sync/codeforces/{profile_id}"]["post"]
        cf_response = cf_endpoint["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("$ref", cf_response)
        self.assertIn("SyncResult", cf_response["$ref"])

        # Check generic endpoint
        generic_endpoint = paths["/sync/{platform}/{profile_id}"]["post"]
        generic_response = generic_endpoint["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("$ref", generic_response)
        self.assertIn("SyncResult", generic_response["$ref"])

    def test_sync_result_schema_exists(self):
        """SyncResult schema should be defined in components."""
        from app.main import app

        schema = app.openapi()
        components = schema["components"]["schemas"]

        self.assertIn("SyncResult", components)

        sync_result = components["SyncResult"]
        self.assertIn("properties", sync_result)

        # Verify key fields exist
        properties = sync_result["properties"]
        expected_fields = [
            "profile_id",
            "platform",
            "problems_created",
            "submissions_created",
            "problems_solved",
            "synced_at",
        ]

        for field in expected_fields:
            self.assertIn(field, properties, f"Field {field} missing from SyncResult")

    def test_openapi_json_endpoint_accessible(self):
        """GET /openapi.json should return valid JSON."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")

        # Should be valid JSON
        data = response.json()
        self.assertIn("openapi", data)
        self.assertIn("paths", data)

    def test_docs_endpoint_accessible(self):
        """GET /docs should return HTML."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/docs")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

        # Should contain Swagger UI
        html = response.text
        self.assertIn("swagger", html.lower())
