"""Offline HTTP-boundary checks for the optional MiniMax LiteLLM template.

Install tests/requirements-litellm.txt, then run:
    python -m unittest discover -s tests -v
"""

import copy
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import httpx
import respx
import yaml

# Configure offline catalog loading and HTTPX before LiteLLM creates clients.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["DISABLE_AIOHTTP_TRANSPORT"] = "True"
import litellm

litellm.telemetry = False
ROOT = Path(__file__).resolve().parents[1]
IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8A"
    "AwMCAO+jRZkAAAAASUVORK5CYII="
)


def minimax_entries():
    text = (ROOT / "litellm_config.yaml").read_text()
    block = text.split("# MiniMax:", 1)[1].split("\n\n", 1)[0]
    entries = block[block.index("# - model_name:") :]
    return yaml.safe_load(
        "\n".join(line.removeprefix("# ") for line in entries.splitlines())
    )


def completion_response(model):
    return {
        "id": "chatcmpl-offline",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "OK"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    }


class MiniMaxTemplateTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, entry, api_base=None, *, chat=False, **kwargs):
        deployment = copy.deepcopy(entry)
        params = deployment["litellm_params"]
        params["api_key"] = "offline-placeholder"
        if api_base:
            params["api_base"] = api_base
        model = params["model"].removeprefix("minimax/")
        settings = yaml.safe_load((ROOT / "litellm_config.yaml").read_text())[
            "litellm_settings"
        ]
        with (
            mock.patch(
                "socket.socket.connect",
                side_effect=AssertionError(
                    "Unexpected network connection in offline test"
                ),
            ),
            mock.patch(
                "socket.getaddrinfo",
                side_effect=AssertionError("Unexpected DNS lookup in offline test"),
            ),
            respx.mock(assert_all_called=True) as transport,
        ):
            reply = httpx.Response(200, json=completion_response(model))
            if kwargs.get("stream"):
                chunks = [
                    {
                        "id": "chatcmpl-offline",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": "OK"},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-offline",
                        "object": "chat.completion.chunk",
                        "created": 1,
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                        "usage": {
                            "prompt_tokens": 2,
                            "completion_tokens": 1,
                            "total_tokens": 3,
                        },
                    },
                ]
                body = (
                    "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks)
                    + "data: [DONE]\n\n"
                )
                reply = httpx.Response(
                    200, content=body, headers={"content-type": "text/event-stream"}
                )
            route = transport.post(params["api_base"] + "/chat/completions").mock(
                return_value=reply
            )
            router = litellm.Router(model_list=[deployment], num_retries=0)
            with mock.patch.multiple(litellm, **settings):
                if chat:
                    response = await router.acompletion(
                        model=deployment["model_name"], **kwargs
                    )
                else:
                    response = await router.aresponses(
                        model=deployment["model_name"], **kwargs
                    )
                if kwargs.get("stream"):
                    response = [event async for event in response]
            self.assertEqual(route.call_count, 1)
            request = route.calls[0].request
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], model)
            self.assertEqual(
                request.headers["authorization"], "Bearer offline-placeholder"
            )
            self.assertNotIn("input", payload)
            return payload, response

    async def test_default_responses_bridge_both_models_and_regions(self):
        entries = minimax_entries()
        self.assertEqual(
            [entry["model_name"] for entry in entries],
            ["MiniMax-M3.1-Flash", "MiniMax-M3"],
        )
        for entry in entries:
            self.assertEqual(entry["model_info"]["mode"], "chat")
            for base in ("https://api.minimax.io/v1", "https://api.minimaxi.com/v1"):
                with self.subTest(model=entry["model_name"], base=base):
                    payload, response = await self.request(entry, base, input="Hello")
                    self.assertEqual(
                        payload["messages"], [{"role": "user", "content": "Hello"}]
                    )
                    for field in (
                        "thinking",
                        "reasoning_effort",
                        "reasoning_split",
                        "service_tier",
                    ):
                        self.assertNotIn(field, payload)
                    self.assertEqual(response.status, "completed")
                    self.assertEqual(response.output[0].content[0].text, "OK")

    async def test_streaming_responses_bridge(self):
        payload, events = await self.request(
            minimax_entries()[0], input="Hello", stream=True
        )
        self.assertTrue(payload["stream"])
        self.assertIn("response.completed", [event.type for event in events])
        deltas = [
            event.delta
            for event in events
            if event.type == "response.output_text.delta"
        ]
        self.assertEqual("".join(deltas), "OK")

    async def test_flash_explicit_reasoning_efforts(self):
        for effort in ("low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort):
                payload, _ = await self.request(
                    minimax_entries()[0], input="Hello", reasoning={"effort": effort}
                )
                self.assertEqual(payload["reasoning_effort"], effort)

    async def test_saved_custom_alias_and_legacy_id_are_not_rewritten(self):
        for model in ("MiniMax-M2.7", "MiniMax-custom-approved"):
            with self.subTest(model=model):
                entry = minimax_entries()[1]
                entry["model_name"] = "saved-minimax"
                entry["litellm_params"]["model"] = "minimax/" + model
                payload, _ = await self.request(
                    entry, input="Continue the saved session"
                )
                self.assertEqual(payload["model"], model)

    async def test_responses_tools_and_image_preserved(self):
        payload, _ = await self.request(
            minimax_entries()[0],
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Describe"},
                        {"type": "input_image", "image_url": IMAGE, "detail": "low"},
                    ],
                }
            ],
            tools=[
                {
                    "type": "function",
                    "name": "inspect",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
        )
        self.assertEqual(
            payload["messages"][0]["content"][1],
            {
                "type": "image_url",
                "image_url": {"url": IMAGE, "detail": "low"},
            },
        )
        self.assertEqual(payload["tools"][0]["function"]["name"], "inspect")

    async def test_chat_multimodal_content_and_m3_thinking_preserved(self):
        content = [
            {"type": "text", "text": "Summarize"},
            {"type": "image_url", "image_url": {"url": IMAGE}},
            {"type": "video_url", "video_url": {"url": "mm_file://offline-video"}},
        ]
        payload, _ = await self.request(
            minimax_entries()[1],
            chat=True,
            messages=[{"role": "user", "content": content}],
            extra_body={
                "thinking": {"type": "disabled"},
                "reasoning_split": False,
                "service_tier": "priority",
            },
        )
        self.assertEqual(payload["messages"][0]["content"], content)
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertFalse(payload["reasoning_split"])
        self.assertEqual(payload["service_tier"], "priority")


if __name__ == "__main__":
    unittest.main()
