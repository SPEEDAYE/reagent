#!/usr/bin/env python3
"""Simple API smoke tests for REagent.

Examples:
  python main.py smoke quick
  python main.py smoke pipeline --stream-seconds 120
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_BASE_URL = "http://localhost:8000"


class SmokeTestError(RuntimeError):
    pass


@dataclass
class Client:
    base_url: str
    user_id: str
    timeout: int

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}{path}"
        response = requests.request(method, url, timeout=self.timeout, **kwargs)
        return response

    def json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, path, **kwargs)
        try:
            payload = response.json()
        except Exception as exc:  # pragma: no cover - smoke-test helper
            raise SmokeTestError(
                f"{method} {path} did not return JSON: {response.text}"
            ) from exc
        if response.status_code >= 400:
            raise SmokeTestError(f"{method} {path} failed: {payload}")
        return payload


def log(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


def check_health(client: Client) -> dict[str, Any]:
    payload = client.json("GET", "/health")
    log("health", payload)
    if payload.get("status") != "healthy":
        raise SmokeTestError(f"health is not healthy: {payload}")
    return payload


def create_project(
    client: Client,
    project_name: str,
    description: str,
    srs_template: str = "Initial",
) -> str:
    payload = client.json(
        "POST",
        "/project/create",
        json={
            "user_id": client.user_id,
            "project_name": project_name,
            "description": description,
            "srs_template": srs_template,
        },
    )
    log("create_project", payload)
    project_id = payload.get("project_id")
    if not project_id:
        raise SmokeTestError(f"missing project_id in response: {payload}")
    return project_id


def delete_project(client: Client, project_id: str) -> None:
    payload = client.json("DELETE", f"/project/{project_id}")
    log("delete_project", payload)


def quick_mode(client: Client) -> None:
    check_health(client)
    project_id = create_project(
        client,
        project_name=f"smoke-quick-{uuid.uuid4().hex[:6]}",
        description="Quick smoke test project",
    )
    try:
        log("list_projects", client.json("GET", f"/project/list/{client.user_id}"))
        log("get_project", client.json("GET", f"/project/{project_id}"))
        artifacts = client.json("GET", f"/artifacts/{project_id}")
        log("artifacts_before_run", artifacts)
        if artifacts.get("completed") != 0:
            raise SmokeTestError(
                f"new project should have 0 completed artifacts: {artifacts}"
            )
    finally:
        delete_project(client, project_id)


def start_pipeline(client: Client, project_id: str, human_request: str | None) -> None:
    payload = client.json(
        "POST",
        "/graph/stream/create",
        json={
            "project_id": project_id,
            "user_id": client.user_id,
            "human_request": human_request,
        },
    )
    log("start_pipeline", payload)


def parse_sse_events(response: requests.Response, max_seconds: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    current_event = "message"
    current_data: list[str] = []
    deadline = time.time() + max_seconds

    for raw_line in response.iter_lines(decode_unicode=True):
        if time.time() > deadline:
            break
        line = raw_line or ""
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            current_data.append(line.split(":", 1)[1].strip())
            continue
        if line == "":
            if current_data:
                joined = "\n".join(current_data)
                try:
                    payload = json.loads(joined)
                except json.JSONDecodeError:
                    payload = {"type": current_event, "raw": joined}
                events.append(payload)
                print(f"[SSE] {json.dumps(payload, ensure_ascii=False)}")
                if payload.get("type") in {"completed", "finished", "error", "interrupt"}:
                    break
            current_event = "message"
            current_data = []

    return events


def pipeline_mode(
    client: Client,
    stream_seconds: int,
    cleanup: bool,
    auto_accept: bool,
) -> None:
    check_health(client)
    project_id = create_project(
        client,
        project_name=f"smoke-pipeline-{uuid.uuid4().hex[:6]}",
        description="Pipeline smoke test project",
    )

    try:
        start_pipeline(client, project_id, human_request="Smoke test run")

        with client.request(
            "GET",
            f"/graph/stream/{project_id}",
            headers={"Accept": "text/event-stream"},
            stream=True,
        ) as response:
            if response.status_code >= 400:
                raise SmokeTestError(
                    f"SSE subscribe failed: {response.status_code} {response.text}"
                )
            events = parse_sse_events(response, stream_seconds)

        if not events:
            raise SmokeTestError("no SSE events received")

        event_types = {event.get("type") for event in events}
        if "stage_start" not in event_types:
            raise SmokeTestError(f"missing stage_start event: {events}")

        if "interrupt" in event_types and auto_accept:
            client.json(
                "POST",
                "/graph/stream/resume",
                json={
                    "project_id": project_id,
                    "resume_type": "accept",
                    "human_comment": "smoke auto accept",
                },
            )
            log("resume_after_interrupt", {"project_id": project_id, "action": "accept"})

        project_payload = client.json("GET", f"/project/{project_id}")
        log("project_after_stream", project_payload)
        if project_payload.get("status") not in {"running", "completed", "finished", "error"}:
            raise SmokeTestError(f"unexpected project status: {project_payload}")

        artifacts_payload = client.json("GET", f"/artifacts/{project_id}")
        log("artifacts_after_stream", artifacts_payload)
        completed = artifacts_payload.get("completed", 0)
        meaningful_events = {"artifact_complete", "interrupt", "completed", "finished", "error"}
        if completed == 0 and not (event_types & meaningful_events):
            raise SmokeTestError(
                "pipeline only reached bootstrap events within the stream window; "
                "no artifact was completed and no interrupt/error/finish event arrived"
            )

    finally:
        if cleanup:
            delete_project(client, project_id)
        else:
            print(f"\nProject kept for inspection: {project_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="REagent API smoke tests")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--user-id", default="smoke_test_user")
    parser.add_argument("--timeout", type=int, default=20)

    subparsers = parser.add_subparsers(dest="mode", required=True)

    subparsers.add_parser("quick", help="Health + project CRUD + artifacts smoke test")

    pipeline = subparsers.add_parser(
        "pipeline",
        help="Create project, start pipeline, consume SSE, inspect status",
    )
    pipeline.add_argument("--stream-seconds", type=int, default=90)
    pipeline.add_argument("--cleanup", action="store_true")
    pipeline.add_argument("--auto-accept", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    client = Client(args.base_url.rstrip("/"), args.user_id, args.timeout)

    try:
        if args.mode == "quick":
            quick_mode(client)
        elif args.mode == "pipeline":
            pipeline_mode(
                client,
                stream_seconds=args.stream_seconds,
                cleanup=args.cleanup,
                auto_accept=args.auto_accept,
            )
        else:  # pragma: no cover - argparse prevents this
            raise SmokeTestError(f"unknown mode: {args.mode}")
    except (requests.RequestException, SmokeTestError) as exc:
        print(f"\nSMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1

    print("\nSMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
