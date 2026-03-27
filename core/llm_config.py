import json
import os
from typing import Dict


class LLMConfigStore:
    def __init__(self, file_path: str = "./data/llm_config.json"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    def default_config(self) -> Dict[str, str]:
        # Backward-compatible defaults for existing users.
        cfg = {
            "mode": "api",  # api | ollama
            "api_url": "",
            "api_key": "",
            "api_model": "deepseek/deepseek-v3.2-251201",
            "ollama_host": "http://127.0.0.1:11434",
            "ollama_model": "qwen2.5:7b",
        }

        # Optional fallback from legacy config.py if present.
        try:
            import config  # type: ignore

            cfg["api_url"] = getattr(config, "API_URL", "") or cfg["api_url"]
            cfg["api_key"] = getattr(config, "API_KEY", "") or cfg["api_key"]
            legacy_model = getattr(config, "API_MODEL", "")
            if legacy_model:
                cfg["api_model"] = legacy_model
        except Exception:
            pass

        return cfg

    def load(self) -> Dict[str, str]:
        cfg = self.default_config()
        if not os.path.exists(self.file_path):
            self.save(cfg)
            return cfg

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            if isinstance(user_cfg, dict):
                cfg.update({k: str(v) for k, v in user_cfg.items() if v is not None})
        except Exception:
            # Keep defaults if malformed.
            pass

        if cfg.get("mode") not in ("api", "ollama"):
            cfg["mode"] = "api"

        cfg["api_url"] = self._normalize_api_url(cfg.get("api_url", ""))
        return cfg

    @staticmethod
    def _normalize_api_url(url: str) -> str:
        """Auto-append /v1/chat/completions if the user only provided a base URL."""
        url = (url or "").strip().rstrip("/")
        if not url:
            return ""
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        # Bare domain like https://hk.linkapi.ai
        if not url.endswith("/v1/chat/completions"):
            return url + "/v1/chat/completions"
        return url

    def save(self, cfg: Dict[str, str]) -> Dict[str, str]:
        normalized = self.default_config()
        normalized.update({k: str(v) for k, v in cfg.items() if v is not None})
        if normalized.get("mode") not in ("api", "ollama"):
            normalized["mode"] = "api"
        normalized["api_url"] = self._normalize_api_url(normalized.get("api_url", ""))

        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)

        return normalized
