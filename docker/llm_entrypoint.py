#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
from huggingface_hub import HfApi


def log(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def parse_repo_and_quant(raw: str) -> tuple[str, str]:
    if not raw:
        raise RuntimeError("MODEL_REPO is empty")
    if ":" in raw:
        repo, quant = raw.rsplit(":", 1)
        return repo, quant.upper()
    return raw, "Q4_K_M"


def find_cached_model(cache_root: Path, quant: str) -> Path | None:
    if not cache_root.exists():
        return None

    ggufs = sorted(cache_root.rglob("*.gguf"))
    if not ggufs:
        return None

    preferred = [p for p in ggufs if quant.lower() in p.name.lower()]
    if preferred:
        return preferred[0]

    return ggufs[0]


def find_remote_model_file(repo_id: str, quant: str) -> str:
    api = HfApi()
    files = api.list_repo_files(repo_id=repo_id, repo_type="model")

    ggufs = sorted(f for f in files if f.lower().endswith(".gguf"))
    if not ggufs:
        raise RuntimeError(f"No GGUF files found in repo: {repo_id}")

    preferred = [f for f in ggufs if quant.lower() in Path(f).name.lower()]
    if preferred:
        return preferred[0]

    return ggufs[0]


def hf_resolve_url(repo_id: str, filename: str) -> str:
    return f"https://huggingface.co/{repo_id}/resolve/main/{filename}?download=true"


def get_remote_size(url: str, headers: dict[str, str]) -> int | None:
    try:
        r = requests.head(url, headers=headers, allow_redirects=True, timeout=30)
        r.raise_for_status()
        value = r.headers.get("Content-Length")
        return int(value) if value else None
    except Exception:
        return None


def download_with_resume(
    url: str,
    dest: Path,
    token: str | None,
    max_retries: int = 10,
    chunk_size: int = 8 * 1024 * 1024,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    total_size = get_remote_size(url, headers)

    for attempt in range(1, max_retries + 1):
        downloaded = part.stat().st_size if part.exists() else 0
        req_headers = dict(headers)

        if downloaded > 0:
            req_headers["Range"] = f"bytes={downloaded}-"

        log({
            "stage": "download_attempt",
            "attempt": attempt,
            "resume_from_bytes": downloaded,
            "target_path": str(dest),
            "total_size_bytes": total_size,
        })

        try:
            with requests.get(url, headers=req_headers, stream=True, allow_redirects=True, timeout=(30, 120)) as r:
                if r.status_code not in (200, 206):
                    raise RuntimeError(f"Unexpected status code: {r.status_code}")

                mode = "ab" if downloaded > 0 else "wb"
                with open(part, mode) as f:
                    last_log_time = time.time()
                    bytes_written = downloaded

                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        f.write(chunk)
                        bytes_written += len(chunk)

                        now = time.time()
                        if now - last_log_time >= 5:
                            percent = None
                            if total_size and total_size > 0:
                                percent = round(bytes_written * 100.0 / total_size, 2)
                            log({
                                "stage": "download_progress",
                                "downloaded_bytes": bytes_written,
                                "total_size_bytes": total_size,
                                "percent": percent,
                                "part_path": str(part),
                            })
                            last_log_time = now

            final_size = part.stat().st_size
            if total_size is not None and final_size < total_size:
                raise RuntimeError(
                    f"Download incomplete: have {final_size} bytes, expected {total_size}"
                )

            part.replace(dest)

            log({
                "stage": "download_complete",
                "model_path": str(dest),
                "size_bytes": dest.stat().st_size,
            })
            return dest

        except Exception as exc:
            log({
                "stage": "download_retry",
                "attempt": attempt,
                "error": str(exc),
            })
            if attempt == max_retries:
                raise
            time.sleep(min(5 * attempt, 30))

    raise RuntimeError("Download failed after retries")


def ensure_model(repo_id: str, quant: str, cache_root: Path, hf_token: str | None) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)

    cached = find_cached_model(cache_root, quant)
    if cached is not None and cached.exists():
        log({
            "stage": "model_cached",
            "model_path": str(cached),
            "size_bytes": cached.stat().st_size,
        })
        return cached

    remote_file = find_remote_model_file(repo_id, quant)
    url = hf_resolve_url(repo_id, remote_file)
    final_path = cache_root / remote_file

    log({
        "stage": "model_download_start",
        "repo_id": repo_id,
        "remote_file": remote_file,
        "url": url,
        "cache_root": str(cache_root),
    })

    return download_with_resume(url, final_path, hf_token)


def main() -> None:
    model_repo_raw = os.getenv("MODEL_REPO", "").strip()
    model_alias = os.getenv("MODEL_ALIAS", "local").strip() or "local"
    hf_token = os.getenv("HF_TOKEN") or None

    ctx_size = os.getenv("CTX_SIZE", "4096")
    n_predict = os.getenv("N_PREDICT", "512")
    n_gpu_layers = os.getenv("N_GPU_LAYERS", "auto")
    batch_size = os.getenv("BATCH_SIZE", "64")
    ubatch_size = os.getenv("UBATCH_SIZE", "32")
    threads = os.getenv("THREADS", "4")
    parallel = os.getenv("PARALLEL", "1")

    cache_root = Path("/models/cache")
    repo_id, quant = parse_repo_and_quant(model_repo_raw)

    log({
        "stage": "resolve_model",
        "repo_id": repo_id,
        "quant": quant,
        "cache_root": str(cache_root),
    })

    model_path = ensure_model(repo_id, quant, cache_root, hf_token)

    cmd = [
        "/app/llama-server",
        "--host", "0.0.0.0",
        "--port", "8080",
        "--model", str(model_path),
        "--alias", model_alias,
        "--ctx-size", str(ctx_size),
        "--n-predict", str(n_predict),
        "--n-gpu-layers", str(n_gpu_layers),
        "--batch-size", str(batch_size),
        "--ubatch-size", str(ubatch_size),
        "--threads", str(threads),
        "--parallel", str(parallel),
        "-v",
    ]

    log({
        "stage": "launch_server",
        "cmd": cmd,
    })

    os.execv(cmd[0], cmd)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"stage": "fatal", "error": str(exc)}, ensure_ascii=False), file=sys.stderr, flush=True)
        raise