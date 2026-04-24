from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import requests
from huggingface_hub import HfApi, hf_hub_url


def log(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def parse_model_repo(value: str) -> tuple[str, str]:
    value = value.strip()
    if not value:
        raise ValueError("MODEL_REPO is empty")

    repo_id, sep, quant = value.rpartition(":")
    if sep and "/" in repo_id:
        return repo_id, quant

    return value, getenv("MODEL_QUANT", "")


def repo_cache_dir(cache_root: Path, repo_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", repo_id)
    return cache_root / safe


def choose_remote_file(
    repo_id: str,
    quant: str,
    explicit_model_file: str | None,
    hf_token: str | None,
) -> str:
    api = HfApi(token=hf_token)

    files = api.list_repo_files(repo_id=repo_id, repo_type="model")
    ggufs = [f for f in files if f.lower().endswith(".gguf")]

    if explicit_model_file:
        if explicit_model_file not in ggufs:
            raise RuntimeError(
                f"MODEL_FILE={explicit_model_file!r} not found in repo {repo_id}. "
                f"Available gguf files: {ggufs}"
            )
        return explicit_model_file

    if not ggufs:
        raise RuntimeError(f"No GGUF files found in repo {repo_id}")

    quant = quant.strip()
    if not quant:
        if len(ggufs) == 1:
            return ggufs[0]
        raise RuntimeError(
            f"MODEL_REPO did not include quant and MODEL_FILE is not set. "
            f"Available gguf files in {repo_id}: {ggufs}"
        )

    def score(filename: str) -> tuple[int, int, str]:
        name = filename.lower()
        q = quant.lower()
        if name.endswith(f"-{q}.gguf"):
            return (0, len(filename), filename)
        if f"-{q}." in name:
            return (1, len(filename), filename)
        if q in name:
            return (2, len(filename), filename)
        return (9, len(filename), filename)

    ranked = sorted(ggufs, key=score)
    if score(ranked[0])[0] >= 9:
        raise RuntimeError(
            f"Could not find GGUF matching quant={quant!r} in repo {repo_id}. "
            f"Available gguf files: {ggufs}"
        )
    return ranked[0]


def find_cached_model(repo_dir: Path, remote_file: str) -> Path | None:
    candidate = repo_dir / remote_file
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def content_length_from_head(url: str, hf_token: str | None) -> int | None:
    headers = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    try:
        r = requests.head(url, headers=headers, allow_redirects=True, timeout=30)
        r.raise_for_status()
        size = r.headers.get("Content-Length")
        return int(size) if size is not None else None
    except Exception:
        return None


def download_with_resume(url: str, final_path: Path, hf_token: str | None) -> Path:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(final_path.suffix + ".part")

    existing = tmp_path.stat().st_size if tmp_path.exists() else 0
    total_size = content_length_from_head(url, hf_token)

    headers = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        if existing > 0 and r.status_code == 200:
            existing = 0
            tmp_path.unlink(missing_ok=True)

        r.raise_for_status()

        if total_size is None:
            content_length = r.headers.get("Content-Length")
            if content_length is not None:
                total_size = int(content_length) + existing

        mode = "ab" if existing > 0 else "wb"
        downloaded = existing
        last_report_time = 0.0
        last_reported = -1

        with open(tmp_path, mode) as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue

                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                should_report = (
                    downloaded != last_reported
                    and (
                        now - last_report_time >= 1.0
                        or (total_size is not None and downloaded >= total_size)
                    )
                )

                if should_report:
                    log(
                        {
                            "stage": "model_download_progress",
                            "path": str(final_path),
                            "downloaded_bytes": downloaded,
                            "total_bytes": total_size,
                            "percent": round(downloaded * 100.0 / total_size, 2)
                            if total_size
                            else None,
                        }
                    )
                    last_report_time = now
                    last_reported = downloaded

    tmp_path.replace(final_path)

    log(
        {
            "stage": "model_download_complete",
            "path": str(final_path),
            "size_bytes": final_path.stat().st_size,
        }
    )
    return final_path


def ensure_model(
    repo_id: str,
    quant: str,
    cache_root: Path,
    hf_token: str | None,
    explicit_model_file: str | None,
) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)

    remote_file = choose_remote_file(repo_id, quant, explicit_model_file, hf_token)
    repo_dir = repo_cache_dir(cache_root, repo_id)
    repo_dir.mkdir(parents=True, exist_ok=True)

    log(
        {
            "stage": "resolve_model",
            "repo_id": repo_id,
            "quant": quant,
            "remote_file": remote_file,
            "cache_root": str(cache_root),
            "repo_dir": str(repo_dir),
        }
    )

    cached = find_cached_model(repo_dir, remote_file)
    if cached is not None:
        log(
            {
                "stage": "model_cached",
                "repo_id": repo_id,
                "model_path": str(cached),
                "size_bytes": cached.stat().st_size,
            }
        )
        return cached

    url = hf_hub_url(repo_id=repo_id, filename=remote_file, repo_type="model")
    final_path = repo_dir / remote_file

    log(
        {
            "stage": "model_download_start",
            "repo_id": repo_id,
            "remote_file": remote_file,
            "target_path": str(final_path),
        }
    )

    return download_with_resume(url, final_path, hf_token)


def build_server_cmd(model_path: Path) -> list[str]:
    server_bin = (
        getenv("LLAMA_SERVER_BIN")
        or shutil.which("llama-server")
        or "/app/llama-server"
    )

    host = getenv("LLAMA_ARG_HOST") or "0.0.0.0"
    port = getenv("LLAMA_ARG_PORT") or "8080"
    alias = getenv("MODEL_ALIAS") or "local"
    ctx_size = getenv("CTX_SIZE") or "4096"
    n_predict = getenv("N_PREDICT") or "1024"
    n_gpu_layers = getenv("N_GPU_LAYERS") or "999"
    batch_size = getenv("BATCH_SIZE") or "256"
    ubatch_size = getenv("UBATCH_SIZE") or "128"
    threads = getenv("THREADS") or "4"
    parallel = getenv("PARALLEL") or "1"

    cmd = [
        server_bin,
        "--host",
        host,
        "--port",
        port,
        "-m",
        str(model_path),
        "--alias",
        alias,
        "--ctx-size",
        ctx_size,
        "--n-predict",
        n_predict,
        "--n-gpu-layers",
        n_gpu_layers,
        "--batch-size",
        batch_size,
        "--ubatch-size",
        ubatch_size,
        "--threads",
        threads,
        "--parallel",
        parallel,
    ]

    if getenv("NO_WARMUP", "0") == "1":
        cmd.append("--no-warmup")

    return cmd


def main() -> None:
    model_repo = getenv("MODEL_REPO")
    model_file = getenv("MODEL_FILE") or None
    hf_token = (
        getenv("HF_TOKEN")
        or getenv("HUGGINGFACE_TOKEN")
        or getenv("HUGGINGFACE_HUB_TOKEN")
        or None
    )

    if not model_repo:
        raise SystemExit("MODEL_REPO is not set")

    repo_id, quant = parse_model_repo(model_repo)
    cache_root = Path(getenv("MODEL_CACHE_ROOT") or "/models/cache")

    model_path = ensure_model(
        repo_id=repo_id,
        quant=quant,
        cache_root=cache_root,
        hf_token=hf_token,
        explicit_model_file=model_file,
    )

    cmd = build_server_cmd(model_path)

    log(
        {
            "stage": "launch_server",
            "repo_id": repo_id,
            "model_path": str(model_path),
            "cmd": cmd,
        }
    )

    os.execvpe(cmd[0], cmd, os.environ.copy())


if __name__ == "__main__":
    main()