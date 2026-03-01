import base64
import json
from pathlib import Path

import requests


class OllamaProvider:
    def __init__(self, host: str = "http://127.0.0.1:11434", timeout: int = 120):
        self.host = host.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _encode_image(path: str) -> str:
        image_path = Path(path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        return base64.b64encode(image_path.read_bytes()).decode("ascii")

    @staticmethod
    def _extract_json(text: str) -> dict:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Ollama response did not include a JSON object")
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
        off_b64 = self._encode_image(offensive_image_path)
        def_b64 = self._encode_image(defensive_image_path)

        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [off_b64, def_b64],
                },
            ],
        }

        response = requests.post(
            f"{self.host}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        content = message.get("content", "")
        return self._extract_json(content)
