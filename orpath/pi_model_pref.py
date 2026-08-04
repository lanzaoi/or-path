"""Pi model preference for OR-Path (watch UI + launch).

Precedence:
1. env ORPATH_PI_MODEL / ORPATH_PI_PROVIDER
2. file ORPATH_HOME/.pi/orpath_model.json
3. .pi/settings.json subagents.defaultModel
4. code defaults
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orpath.paths import orpath_home

# Shown in Watch model picker (provider, model, label_zh)
MODEL_PRESETS: list[dict[str, str]] = [
    {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "label": "DeepSeek V4 Flash（默认·快）",
    },
    {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "label": "DeepSeek V4 Pro（更强）",
    },
    {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "label": "DeepSeek Chat",
    },
]

_FALLBACK_PROVIDER = "deepseek"
_FALLBACK_MODEL = "deepseek-v4-flash"


def _pref_path(home: Path | None = None) -> Path:
    h = Path(home or orpath_home())
    return h / ".pi" / "orpath_model.json"


def _read_settings_default(home: Path) -> tuple[str, str]:
    p = home / ".pi" / "settings.json"
    if not p.is_file():
        return _FALLBACK_PROVIDER, _FALLBACK_MODEL
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _FALLBACK_PROVIDER, _FALLBACK_MODEL
    sub = data.get("subagents") if isinstance(data, dict) else None
    model = ""
    if isinstance(sub, dict):
        model = str(sub.get("defaultModel") or "").strip()
    orp = data.get("orpath") if isinstance(data, dict) else None
    provider = _FALLBACK_PROVIDER
    if isinstance(orp, dict):
        provider = str(orp.get("piDefaultProvider") or provider).strip() or provider
        if not model:
            model = str(orp.get("piDefaultModel") or "").strip()
    if not model:
        model = _FALLBACK_MODEL
    return provider, model


def get_pi_model_pref(*, home: Path | None = None) -> dict[str, Any]:
    """Return current effective provider/model + presets + source."""
    h = Path(home or orpath_home())
    source = "default"
    provider = os.environ.get("ORPATH_PI_PROVIDER", "").strip()
    model = os.environ.get("ORPATH_PI_MODEL", "").strip()
    if provider and model:
        source = "env"
    else:
        fp = _pref_path(h)
        if fp.is_file():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    provider = provider or str(data.get("provider") or "").strip()
                    model = model or str(data.get("model") or "").strip()
                    if provider or model:
                        source = "file"
            except (OSError, json.JSONDecodeError):
                pass
        if not provider or not model:
            sp, sm = _read_settings_default(h)
            provider = provider or sp
            model = model or sm
            if source == "default":
                source = "settings" if (h / ".pi" / "settings.json").is_file() else "default"
    provider = provider or _FALLBACK_PROVIDER
    model = model or _FALLBACK_MODEL
    return {
        "provider": provider,
        "model": model,
        "source": source,
        "presets": list(MODEL_PRESETS),
        "pref_path": str(_pref_path(h)),
        "note": "仅影响本机随后启动的 Pi 会话；不改写已结束的 run。",
    }


def set_pi_model_pref(
    *,
    provider: str,
    model: str,
    home: Path | None = None,
    sync_settings: bool = True,
) -> dict[str, Any]:
    """Persist preference to file + process env (+ optional .pi/settings.json)."""
    h = Path(home or orpath_home())
    provider = (provider or "").strip() or _FALLBACK_PROVIDER
    model = (model or "").strip() or _FALLBACK_MODEL
    if not model or "/" in model and model.count("/") > 2:
        raise ValueError("invalid model name")
    # basic allow: known presets or deepseek-* 
    allowed = {(p["provider"], p["model"]) for p in MODEL_PRESETS}
    if (provider, model) not in allowed and not model.startswith("deepseek"):
        # still allow other deepseek-like; block empty nonsense
        if len(model) < 3 or len(model) > 80:
            raise ValueError(f"unsupported model: {model}")

    payload = {
        "provider": provider,
        "model": model,
        "updated_note": "set via OR-Path Watch / set_pi_model_pref",
    }
    path = _pref_path(h)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    os.environ["ORPATH_PI_PROVIDER"] = provider
    os.environ["ORPATH_PI_MODEL"] = model

    if sync_settings:
        sp = h / ".pi" / "settings.json"
        data: dict[str, Any] = {}
        if sp.is_file():
            try:
                raw = json.loads(sp.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data = raw
            except (OSError, json.JSONDecodeError):
                data = {}
        sub = data.get("subagents")
        if not isinstance(sub, dict):
            sub = {}
        sub["defaultModel"] = model
        data["subagents"] = sub
        orp = data.get("orpath")
        if not isinstance(orp, dict):
            orp = {}
        orp["piDefaultModel"] = model
        orp["piDefaultProvider"] = provider
        data["orpath"] = orp
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return get_pi_model_pref(home=h)


def resolve_launch_model(
    provider: str | None = None,
    model: str | None = None,
    *,
    home: Path | None = None,
) -> tuple[str, str]:
    """Effective (provider, model) for a Pi launch."""
    pref = get_pi_model_pref(home=home)
    p = (provider or "").strip() or pref["provider"]
    m = (model or "").strip() or pref["model"]
    return str(p), str(m)
