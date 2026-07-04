from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from src.core.config import get_settings
from src.providers.base import ResearchClientError, json_request


@dataclass
class OpenAIChatClient:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1/chat/completions"

    def json_completion(self, developer_prompt: str, user_prompt: str) -> Dict[str, Any]:
        settings = get_settings()
        response = json_request(
            method="POST",
            url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload={
                "model": self.model,
                "temperature": settings.provider_runtime.openai_temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "developer", "content": developer_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        message = response.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "{}")
        if not isinstance(content, str):
            raise ResearchClientError("OpenAI returned a non-text completion")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ResearchClientError("OpenAI returned invalid JSON") from exc

        usage = response.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0)
        estimated_cost_usd = round((prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006), 8)
        return {
            "payload": payload,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": estimated_cost_usd,
            },
        }
