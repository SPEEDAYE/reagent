import base64
import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.auth import CurrentUser, decode_access_token, require_project_owner, resolve_user_id
from backend.config import settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


class _ProjectsCollection:
    def __init__(self, projects):
        self.projects = projects

    async def find_one(self, query, projection):
        for project in self.projects:
            if all(project.get(key) == value for key, value in query.items()):
                return dict(project)
        return None


class AuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_secret = settings.AUTH_TOKEN_SECRET
        self.original_required = settings.AUTH_REQUIRED

    def tearDown(self):
        settings.AUTH_TOKEN_SECRET = self.original_secret
        settings.AUTH_REQUIRED = self.original_required

    def test_two_part_gateway_token_is_verified(self):
        settings.AUTH_TOKEN_SECRET = "test-secret"
        claims = {
            "userCode": "user-100",
            "username": "alice",
            "roles": ["user"],
            "expiresAt": 4_102_444_800,
        }
        payload = _b64url(json.dumps(claims).encode("utf-8"))
        signature = _b64url(
            hmac.new(b"test-secret", payload.encode("ascii"), hashlib.sha256).digest()
        )

        user = decode_access_token(f"{payload}.{signature}")

        self.assertEqual(user.user_id, "user-100")
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.roles, ("user",))

    def test_authenticated_user_cannot_spoof_legacy_user_id(self):
        with self.assertRaises(HTTPException) as caught:
            resolve_user_id(CurrentUser("alice"), "bob")
        self.assertEqual(caught.exception.status_code, 403)

    async def test_project_owner_can_access_project(self):
        collection = _ProjectsCollection(
            [{"project_id": "p1", "user_id": "alice", "status": "created"}]
        )
        with patch("backend.auth.projects_col", return_value=collection):
            project = await require_project_owner("p1", CurrentUser("alice"))
        self.assertEqual(project["project_id"], "p1")

    async def test_foreign_project_is_hidden_as_not_found(self):
        collection = _ProjectsCollection(
            [{"project_id": "p1", "user_id": "alice", "status": "created"}]
        )
        with patch("backend.auth.projects_col", return_value=collection):
            with self.assertRaises(HTTPException) as caught:
                await require_project_owner("p1", CurrentUser("bob"))
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
