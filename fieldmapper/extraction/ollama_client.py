from __future__ import annotations

import requests


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def chat(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
        timeout: int = 1800,
    ) -> str:
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": temperature},
        }
        resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    def embeddings(self, model: str, text: str) -> list[float]:
        payload = {"model": model, "prompt": text}
        resp = requests.post(f"{self.base_url}/api/embeddings", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        emb = data.get("embedding")
        if not emb:
            raise ValueError("Embedding response missing 'embedding' field")
        return emb

    def list_models(self) -> list[str]:
        resp = requests.get(f"{self.base_url}/api/tags", timeout=20)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        names = []
        for item in models:
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
        return names
