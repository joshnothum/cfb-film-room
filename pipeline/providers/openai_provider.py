import base64
import json
import os
from pathlib import Path

import requests


class OpenAIProvider:
    def __init__(self, api_key: str | None = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.timeout = timeout

    @staticmethod
    def _encode_image(path: str) -> str:
        image_path = Path(path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        data = image_path.read_bytes()
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _extract_json(text: str) -> dict:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("OpenAI response was empty")

        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("OpenAI response did not include a JSON object")
        return json.loads(cleaned[start : end + 1])

    def generate_feedback(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        offensive_image_path: str,
        defensive_image_path: str,
        model: str,
    ) -> dict:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for provider=openai")

        off_b64 = self._encode_image(offensive_image_path)
        def_b64 = self._encode_image(defensive_image_path)

        payload = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        {"type": "input_text", "text": "Offensive play image:"},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{off_b64}",
                        },
                        {"type": "input_text", "text": "Defensive play image:"},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{def_b64}",
                        },
                    ],
                },
            ],
        }

        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        output_text = data.get("output_text")
        if not output_text:
            # Fallback path for response payload variants.
            chunks: list[str] = []
            for item in data.get("output", []):
                for content in item.get("content", []):
                    text = content.get("text")
                    if text:
                        chunks.append(text)
            output_text = "\n".join(chunks)

        return self._extract_json(output_text)
