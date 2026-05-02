from __future__ import annotations

import hashlib
import logging
import time

import httpx


class LinearReporter:
    def __init__(
        self,
        api_key: str | None,
        team_id: str | None,
        project_id: str | None,
        logger: logging.Logger,
    ) -> None:
        self.api_key = api_key
        self.team_id = team_id
        self.project_id = project_id
        self.logger = logger
        self.seen: dict[str, list[float]] = {}
        self.threshold = 5
        self.window_seconds = 5 * 60

    async def report_exception(self, title: str, description: str, error_message: str) -> None:
        if not self.api_key or not self.team_id:
            return
        error_hash = hashlib.sha256(f"{title}:{error_message}".encode()).hexdigest()
        now = time.time()
        timestamps = [ts for ts in self.seen.get(error_hash, []) if now - ts <= self.window_seconds]
        timestamps.append(now)
        self.seen[error_hash] = timestamps
        if len(timestamps) < self.threshold:
            return

        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) { success issue { id } }
        }
        """
        input_data = {
            "teamId": self.team_id,
            "title": title,
            "description": f"{description}\n\n<!-- Error Hash: {error_hash} -->",
        }
        if self.project_id:
            input_data["projectId"] = self.project_id
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.linear.app/graphql",
                    headers={"Authorization": self.api_key, "Content-Type": "application/json"},
                    json={"query": mutation, "variables": {"input": input_data}},
                )
                response.raise_for_status()
        except Exception:
            self.logger.exception("Failed to report error to Linear")
