"""Unit tests for cli-anything-mailchimp core modules."""

from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

import responses as resp_lib
import requests

# ── client tests ──────────────────────────────────────────────────────


class TestServerPrefix(unittest.TestCase):
    def test_extracts_suffix(self):
        from cli_anything.mailchimp.core.client import _server_prefix

        assert _server_prefix("abc123-us8") == "us8"
        assert _server_prefix("xyz-eu2") == "eu2"

    def test_missing_suffix_raises(self):
        from cli_anything.mailchimp.core.client import _server_prefix

        with self.assertRaises(ValueError):
            _server_prefix("nodashinkey")


class TestSubscriberHash(unittest.TestCase):
    def test_md5_lowercased(self):
        from cli_anything.mailchimp.core.client import subscriber_hash

        # Known MD5 of "test@example.com"
        assert subscriber_hash("test@example.com") == "55502f40dc8b7c769880b10874abc9d0"
        # Should normalise to lowercase before hashing
        assert subscriber_hash("TEST@EXAMPLE.COM") == subscriber_hash("test@example.com")

    def test_strips_whitespace(self):
        from cli_anything.mailchimp.core.client import subscriber_hash

        assert subscriber_hash("  test@example.com  ") == subscriber_hash("test@example.com")


class TestMailchimpClient(unittest.TestCase):
    def _make_client(self, key: str = "testkey-us1"):
        from cli_anything.mailchimp.core.client import MailchimpClient

        return MailchimpClient(api_key=key)

    def test_base_url(self):
        client = self._make_client("abc-us8")
        assert client._base == "https://us8.api.mailchimp.com/3.0"

    def test_auth_header(self):
        client = self._make_client("abc-us8")
        assert client._session.auth == ("anystring", "abc-us8")

    def test_missing_key_raises_auth_error(self):
        from cli_anything.mailchimp.core.client import MailchimpClient, MailchimpAuthError
        import os

        orig = os.environ.pop("MAILCHIMP_API_KEY", None)
        try:
            with self.assertRaises(MailchimpAuthError):
                MailchimpClient(api_key=None)
        finally:
            if orig:
                os.environ["MAILCHIMP_API_KEY"] = orig

    def test_get_client_exits_on_missing_key(self):
        from cli_anything.mailchimp.core.client import get_client
        import os

        orig = os.environ.pop("MAILCHIMP_API_KEY", None)
        try:
            with self.assertRaises(SystemExit):
                get_client()
        finally:
            if orig:
                os.environ["MAILCHIMP_API_KEY"] = orig

    @resp_lib.activate
    def test_get_success(self):
        from cli_anything.mailchimp.core.client import MailchimpClient

        client = MailchimpClient(api_key="key-us1")
        resp_lib.add(
            resp_lib.GET,
            "https://us1.api.mailchimp.com/3.0/ping",
            json={"health_status": "Everything's Chimpy!"},
            status=200,
        )
        result = client.get("/ping")
        assert result["health_status"] == "Everything's Chimpy!"

    @resp_lib.activate
    def test_get_error_raises(self):
        from cli_anything.mailchimp.core.client import MailchimpClient, MailchimpError

        client = MailchimpClient(api_key="key-us1")
        resp_lib.add(
            resp_lib.GET,
            "https://us1.api.mailchimp.com/3.0/lists/bad",
            json={"title": "Resource Not Found", "detail": "The requested resource could not be found.", "status": 404},
            status=404,
        )
        with self.assertRaises(MailchimpError) as ctx:
            client.get("/lists/bad")
        assert ctx.exception.status == 404
        assert "Resource Not Found" in ctx.exception.title

    @resp_lib.activate
    def test_post_success(self):
        from cli_anything.mailchimp.core.client import MailchimpClient

        client = MailchimpClient(api_key="key-us1")
        resp_lib.add(
            resp_lib.POST,
            "https://us1.api.mailchimp.com/3.0/lists",
            json={"id": "abc123", "name": "My List"},
            status=200,
        )
        result = client.post("/lists", json={"name": "My List"})
        assert result["id"] == "abc123"

    @resp_lib.activate
    def test_delete_returns_ok(self):
        from cli_anything.mailchimp.core.client import MailchimpClient

        client = MailchimpClient(api_key="key-us1")
        resp_lib.add(
            resp_lib.DELETE,
            "https://us1.api.mailchimp.com/3.0/lists/abc123",
            status=204,
        )
        result = client.delete("/lists/abc123")
        assert result == {"ok": True}

    def test_patch_forwards_query_params(self):
        from cli_anything.mailchimp.core.client import MailchimpClient

        client = MailchimpClient(api_key="key-us1")
        client._session.patch = MagicMock()
        client._session.patch.return_value.ok = True
        client._session.patch.return_value.json.return_value = {"id": "contact-1"}

        result = client.patch(
            "/audiences/audience-1/contacts/contact-1",
            json={"email_address": "user@example.com"},
            params={"data_mode": "sync"},
        )

        assert result == {"id": "contact-1"}
        client._session.patch.assert_called_once_with(
            "https://us1.api.mailchimp.com/3.0/audiences/audience-1/contacts/contact-1",
            json={"email_address": "user@example.com"},
            params={"data_mode": "sync"},
            timeout=30,
        )

    def test_put_forwards_query_params(self):
        from cli_anything.mailchimp.core.client import MailchimpClient

        client = MailchimpClient(api_key="key-us1")
        client._session.put = MagicMock()
        client._session.put.return_value.ok = True
        client._session.put.return_value.json.return_value = {"id": "member-1"}

        result = client.put(
            "/lists/list-1/members/hash-1",
            json={"email_address": "user@example.com"},
            params={"skip_merge_validation": True},
        )

        assert result == {"id": "member-1"}
        client._session.put.assert_called_once_with(
            "https://us1.api.mailchimp.com/3.0/lists/list-1/members/hash-1",
            json={"email_address": "user@example.com"},
            params={"skip_merge_validation": True},
            timeout=30,
        )

    def test_delete_forwards_query_params(self):
        from cli_anything.mailchimp.core.client import MailchimpClient

        client = MailchimpClient(api_key="key-us1")
        client._session.delete = MagicMock()
        client._session.delete.return_value.ok = True

        result = client.delete("/lists/list-1", params={"force": True})

        assert result == {"ok": True}
        client._session.delete.assert_called_once_with(
            "https://us1.api.mailchimp.com/3.0/lists/list-1",
            params={"force": True},
            timeout=30,
        )


# ── pagination tests ──────────────────────────────────────────────────


class TestPagination(unittest.TestCase):
    def _mock_client(self, pages: list[list]) -> MagicMock:
        client = MagicMock()
        side_effects = [
            {"lists": page, "total_items": sum(len(p) for p in pages)}
            for page in pages
        ]
        client.get.side_effect = side_effects
        return client

    def test_single_page(self):
        from cli_anything.mailchimp.core.pagination import paginate

        client = self._mock_client([[{"id": "1"}, {"id": "2"}]])
        items = list(paginate(client, "/lists", "lists", page_size=100))
        assert items == [{"id": "1"}, {"id": "2"}]
        assert client.get.call_count == 1

    def test_multiple_pages(self):
        from cli_anything.mailchimp.core.pagination import paginate

        page1 = [{"id": str(i)} for i in range(5)]
        page2 = [{"id": str(i)} for i in range(5, 8)]
        client = self._mock_client([page1, page2])
        items = list(paginate(client, "/lists", "lists", page_size=5))
        assert len(items) == 8
        assert client.get.call_count == 2

    def test_empty_result(self):
        from cli_anything.mailchimp.core.pagination import paginate

        client = self._mock_client([[]])
        items = list(paginate(client, "/lists", "lists"))
        assert items == []

    def test_exact_page_boundary_no_extra_fetch(self):
        """When total_items == page_size, paginator must not fetch a second empty page (I6 fix)."""
        from cli_anything.mailchimp.core.pagination import paginate

        page = [{"id": str(i)} for i in range(5)]
        client = MagicMock()
        # First call returns exactly page_size items with total_items matching
        client.get.return_value = {"lists": page, "total_items": 5}
        items = list(paginate(client, "/lists", "lists", page_size=5))
        assert len(items) == 5
        assert client.get.call_count == 1  # must not make a second call

    def test_collect_returns_total(self):
        from cli_anything.mailchimp.core.pagination import collect

        client = MagicMock()
        client.get.return_value = {"lists": [{"id": "1"}], "total_items": 42}
        items, total = collect(client, "/lists", "lists")
        assert items == [{"id": "1"}]
        assert total == 42


# ── output tests ──────────────────────────────────────────────────────


class TestOutput(unittest.TestCase):
    def setUp(self):
        import cli_anything.mailchimp.utils.output as out
        self._orig = out.USE_JSON
        out.USE_JSON = False

    def tearDown(self):
        import cli_anything.mailchimp.utils.output as out
        out.USE_JSON = self._orig

    def test_json_mode_outputs_json(self):
        import cli_anything.mailchimp.utils.output as out
        import io

        out.USE_JSON = True
        captured = io.StringIO()
        with patch("builtins.print", lambda *a, **kw: captured.write(str(a[0]) + "\n")):
            out._out({"key": "value"})

        parsed = json.loads(captured.getvalue())
        assert parsed["key"] == "value"

    def test_out_list_json(self):
        import cli_anything.mailchimp.utils.output as out
        import io

        out.USE_JSON = True
        captured = io.StringIO()
        with patch("builtins.print", lambda *a, **kw: captured.write(str(a[0]) + "\n")):
            out._out_list([{"id": "1"}, {"id": "2"}], 2)

        parsed = json.loads(captured.getvalue())
        assert parsed["total_items"] == 2
        assert len(parsed["results"]) == 2


# ── smoke import tests ────────────────────────────────────────────────


class TestGeneratedCommandsImport(unittest.TestCase):
    """Verify every generated command module imports cleanly and registers commands.

    This catches codegen regressions like C1 (builtin shadowing) which would
    cause Click to fail silently or raise at import time.
    """

    def test_all_groups_importable(self):
        from cli_anything.mailchimp.commands import ALL_GROUPS

        assert len(ALL_GROUPS) == 30, f"Expected 30 groups, got {len(ALL_GROUPS)}"
        for group in ALL_GROUPS:
            assert group.name is not None
            assert len(group.commands) > 0, f"Group {group.name!r} has no commands"

    def test_no_builtin_shadowing_in_function_names(self):
        """Ensure generated functions are prefixed with _cmd_ (not builtins)."""
        import glob
        import ast
        import builtins as _builtins

        builtin_names = set(dir(_builtins))
        issues = []

        for path in glob.glob("cli_anything/mailchimp/commands/*.py"):
            tree = ast.parse(open(path).read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name in builtin_names:
                        issues.append(f"{path}: def {node.name}()")

        assert not issues, "Builtin shadowing in generated code:\n" + "\n".join(issues)

    def test_all_commands_have_extra_params(self):
        """Every generated command must accept --extra-params (I3 fix)."""
        from cli_anything.mailchimp.commands import ALL_GROUPS
        import click

        missing = []
        for group in ALL_GROUPS:
            for cmd_name, cmd in group.commands.items():
                if isinstance(cmd, click.Group):
                    continue
                param_names = [p.name for p in cmd.params]
                if "extra_params" not in param_names:
                    missing.append(f"{group.name} {cmd_name}")

        assert not missing, "--extra-params missing on:\n" + "\n".join(missing)

    def test_generated_patch_command_forwards_query_params(self):
        from click.testing import CliRunner
        from cli_anything.mailchimp.commands.audiences import audiences_group

        client = MagicMock()
        client.patch.return_value = {"id": "contact-1"}

        with patch("cli_anything.mailchimp.core.client.get_client", return_value=client):
            result = CliRunner().invoke(
                audiences_group,
                [
                    "update",
                    "audience-1",
                    "contact-1",
                    "--data",
                    '{"email_address":"user@example.com"}',
                    "--data-mode",
                    "sync",
                ],
            )

        assert result.exit_code == 0, result.output
        client.patch.assert_called_once_with(
            "/audiences/audience-1/contacts/contact-1",
            json={"email_address": "user@example.com"},
            params={"data_mode": "sync"},
        )

    def test_generated_put_command_forwards_query_params(self):
        from click.testing import CliRunner
        from cli_anything.mailchimp.commands.lists import lists_group

        client = MagicMock()
        client.put.return_value = {"id": "member-1"}

        with patch("cli_anything.mailchimp.core.client.get_client", return_value=client):
            result = CliRunner().invoke(
                lists_group,
                [
                    "update-3",
                    "list-1",
                    "hash-1",
                    "--data",
                    '{"email_address":"user@example.com"}',
                    "--skip-merge-validation",
                    "true",
                ],
            )

        assert result.exit_code == 0, result.output
        client.put.assert_called_once_with(
            "/lists/list-1/members/hash-1",
            json={"email_address": "user@example.com"},
            params={"skip_merge_validation": True},
        )


if __name__ == "__main__":
    unittest.main()
