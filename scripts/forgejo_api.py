"""Minimal Forgejo issues API client shared by the issue scripts (stdlib only)."""

import json
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 20
PAGE = 50

# Errors callers should report rather than crash on.
ApiError = (urllib.error.URLError, OSError, ValueError)


def describe(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code} {exc.read().decode(errors='replace')[:120]}"
    return str(exc)


class Forgejo:
    def __init__(self, base_url, repo, token=""):
        self.base = f"{base_url.rstrip('/')}/api/v1/repos/{repo}"
        self.web = f"{base_url.rstrip('/')}/{repo}"
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    def call(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, headers=self.headers, method=method
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read() or b"null")

    def issues(self, state="open"):
        """All issues (not pull requests) in the given state, every page."""
        found, page = [], 1
        while True:
            query = urllib.parse.urlencode(
                {"state": state, "type": "issues", "limit": PAGE, "page": page}
            )
            batch = self.call("GET", f"/issues?{query}") or []
            found.extend(i for i in batch if i.get("pull_request") is None)
            if len(batch) < PAGE:
                return found
            page += 1

    def create_issue(self, title, body):
        return self.call("POST", "/issues", {"title": title, "body": body})

    def comment(self, number, body):
        return self.call("POST", f"/issues/{number}/comments", {"body": body})

    def close(self, number):
        return self.call("PATCH", f"/issues/{number}", {"state": "closed"})

    def update(self, number, **fields):
        return self.call("PATCH", f"/issues/{number}", fields)

    def pin(self, number):
        return self.call("POST", f"/issues/{number}/pin")
