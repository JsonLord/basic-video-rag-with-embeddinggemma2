"""Synthetic OpenAI and A2A wire fixtures; never import from production code."""

import json
import httpx
import pytest


def packet(delta=None, finish=None):
    return (
        "data: "
        + json.dumps(
            {
                "model": "fixture-qwen",
                "choices": [
                    {"index": 0, "delta": delta or {}, "finish_reason": finish}
                ],
            }
        )
        + "\n\n"
    )


def completion(text):
    return (
        packet({"content": text[:5]})
        + packet({"content": text[5:]}, "stop")
        + "data: [DONE]\n\n"
    )


def calls(parts):
    result = packet({"content": "Checking evidence. "})
    for index, (name, args) in enumerate(parts):
        encoded = json.dumps(args)
        result += packet(
            {
                "tool_calls": [
                    {
                        "index": index,
                        "id": "call_" + str(index),
                        "type": "function",
                        "function": {"name": name, "arguments": encoded[:3]},
                    }
                ]
            }
        )
        result += packet(
            {"tool_calls": [{"index": index, "function": {"arguments": encoded[3:]}}]}
        )
    return result + packet(finish="tool_calls") + "data: [DONE]\n\n"


class WireAgent:
    def __init__(self):
        self.submissions = 0
        self.cancelled = 0
        self.polls = 0
        self.malicious = False
        self.lost = False
        self.bad_url = False
        self.denied = False

    def task(self, state):
        t = {
            "id": "remote-task-1",
            "contextId": "remote-context-1",
            "kind": "task",
            "status": {"state": state},
        }
        if state == "completed":
            output = {
                "text": "Clear the workbench before assembly.",
                "citations": [
                    {"url": "https://docs.example/safety", "title": "Safety guide"}
                ],
            }
            if self.malicious:
                output["citations"][0]["url"] = "javascript:alert(1)"
            t["artifacts"] = [
                {
                    "artifactId": "answer",
                    "parts": [{"kind": "text", "text": json.dumps(output)}],
                }
            ]
        return t

    def __call__(self, request):
        assert request.url.host == "agent.example"
        assert "/a2a/t-synthetic-path-key-12345" in request.url.path
        assert "authorization" not in request.headers
        if self.denied:
            return httpx.Response(401)
        if request.method == "GET":
            if request.url.path.endswith("agent-card.json"):
                return httpx.Response(404)
            return httpx.Response(
                200,
                json={
                    "name": "Agent Zero fixture",
                    "description": "untrusted description",
                    "url": "https://evil.example"
                    if self.bad_url
                    else "https://agent.example/a2a/t-synthetic-path-key-12345",
                    "version": "fixture-1",
                    "protocolVersion": "0.3.0",
                    "capabilities": {"streaming": True},
                    "defaultInputModes": ["text/plain"],
                    "defaultOutputModes": ["application/json"],
                    "skills": [
                        {
                            "id": "research",
                            "name": "Research",
                            "description": "untrusted",
                            "tags": [],
                        }
                    ],
                },
            )
        body = json.loads(request.content)
        method = body["method"]
        if method == "message/send":
            self.submissions += 1
            assert body["params"]["configuration"]["blocking"] is False
            assert "image" not in request.content.decode()
            if self.lost:
                raise httpx.ReadTimeout("synthetic response lost")
            task = self.task("working")
        elif method == "tasks/get":
            self.polls += 1
            task = self.task("completed")
        elif method == "tasks/cancel":
            self.cancelled += 1
            task = self.task("canceled")
        else:
            pytest.fail(method)
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": task}
        )
