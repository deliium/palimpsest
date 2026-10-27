"""Fresh-process supervision for V3 scale benchmark workers.

The supervisor enforces a wall-clock deadline and, where the platform exposes
per-process RSS, a memory budget. It records truthful incomplete outcomes and
never claims that a heartbeat is a completed scientific run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import IO, Final

from tests.benchmarks.v3_measurement import (
    V3ScaleMeasurement,
    V3ScaleMeasurementError,
    V3ScaleStatus,
    incomplete_measurement,
    read_measurement,
)
from tests.benchmarks.v3_workloads import V3ScaleWorkload

_LOG: Final[logging.Logger] = logging.getLogger("scale.v3.supervisor")

WORKER_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_WORKER"
RESULT_PATH_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_RESULT_PATH"
HEARTBEAT_PATH_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_HEARTBEAT_PATH"
WORKLOAD_ID_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_WORKLOAD_ID"
OUTPUT_DIR_ENV: Final[str] = "PALIMPSEST_SCALE_BENCH_OUTPUT"
COVERAGE_FILE_ENV: Final[str] = "COVERAGE_FILE"

_POLL_SECONDS: Final[float] = 0.05
_SHUTDOWN_GRACE_SECONDS: Final[float] = 2.0
_STREAM_CAPTURE_BYTES: Final[int] = 16 * 1024


@dataclass(frozen=True, slots=True)
class V3WorkerSpec:
    """Explicit worker launch identity."""

    workload: V3ScaleWorkload
    command: tuple[str, ...]
    output_dir: Path
    attempt: str
    environment: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if type(self.workload) is not V3ScaleWorkload:
            raise TypeError("workload must be V3ScaleWorkload")
        if not self.workload.executes:
            raise ValueError("query-only workloads are not executable workers")
        if not isinstance(self.command, tuple) or not self.command:
            raise ValueError("command must be a non-empty tuple")
        for item in self.command:
            if type(item) is not str or not item:
                raise ValueError("command entries must be non-empty strings")
        if not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be pathlib.Path")
        if type(self.attempt) is not str or not self.attempt.strip():
            raise ValueError("attempt must be a non-empty string")
        if "/" in self.attempt or "\\" in self.attempt:
            raise ValueError("attempt must be a single path segment")
        if self.environment is not None and not isinstance(self.environment, Mapping):
            raise TypeError("environment must be a mapping or None")


@dataclass(frozen=True, slots=True)
class _AttemptPaths:
    root: Path
    result: Path
    heartbeat: Path
    coverage: Path
    stdout: Path
    stderr: Path


def attempt_paths(spec: V3WorkerSpec) -> _AttemptPaths:
    if not isinstance(spec, V3WorkerSpec):
        raise TypeError("spec must be V3WorkerSpec")
    safe_workload = spec.workload.workload_id.replace("/", "-")
    root = spec.output_dir / safe_workload / spec.attempt
    coverage = root / "coverage.data"
    return _AttemptPaths(
        root=root,
        result=root / "measurement.json",
        heartbeat=root / "heartbeat.json",
        coverage=coverage,
        stdout=root / "stdout.log",
        stderr=root / "stderr.log",
    )


def worker_environment(spec: V3WorkerSpec) -> dict[str, str]:
    """Environment for a child worker; includes the recursive-spawn guard."""
    paths = attempt_paths(spec)
    environment = dict(os.environ)
    if spec.environment:
        environment.update(spec.environment)
    environment[WORKER_ENV] = "1"
    environment[RESULT_PATH_ENV] = str(paths.result)
    environment[HEARTBEAT_PATH_ENV] = str(paths.heartbeat)
    environment[WORKLOAD_ID_ENV] = spec.workload.workload_id
    environment[OUTPUT_DIR_ENV] = str(spec.output_dir)
    environment[COVERAGE_FILE_ENV] = str(paths.coverage)
    return environment


def write_heartbeat(path: Path, *, last_verified_boundary: int) -> None:
    """Atomically publish a verified boundary; a heartbeat is not completion."""
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if type(last_verified_boundary) is not int or last_verified_boundary < 0:
        raise ValueError("last_verified_boundary must be a non-negative integer")
    document = {"last_verified_boundary": last_verified_boundary}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(document, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_heartbeat_boundary(path: Path) -> int:
    """Return the last verified boundary, or ``-1`` when unavailable."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return -1
    if not isinstance(document, dict):
        return -1
    if set(document) != {"last_verified_boundary"}:
        return -1
    value = document["last_verified_boundary"]
    if type(value) is not int or value < 0:
        return -1
    return value


def run_scale_worker(
    spec: V3WorkerSpec,
    *,
    timeout_seconds: float,
    max_rss_bytes: int | None,
) -> V3ScaleMeasurement:
    """Run one fresh worker process and classify its truthful outcome."""
    if os.environ.get(WORKER_ENV) == "1":
        raise RuntimeError("recursive_scale_worker_spawn_denied")
    if not isinstance(spec, V3WorkerSpec):
        raise TypeError("spec must be V3WorkerSpec")
    if type(timeout_seconds) is not float or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be a positive float")
    if max_rss_bytes is not None and (
        type(max_rss_bytes) is not int or max_rss_bytes <= 0
    ):
        raise ValueError("max_rss_bytes must be a positive integer or None")
    paths = attempt_paths(spec)
    if paths.root.exists():
        raise FileExistsError(f"attempt namespace already exists: {paths.root}")
    paths.root.mkdir(parents=True, exist_ok=False)
    environment = worker_environment(spec)
    rss_supported = _rss_supported()
    enforcement = (
        "enforced" if max_rss_bytes is not None and rss_supported else ("unenforced")
    )
    started = time.monotonic()
    _LOG.info(
        "v3_worker_launch workload_id=%s attempt=%s timeout_s=%s rss_budget=%s "
        "rss_enforcement=%s",
        spec.workload.workload_id,
        spec.attempt,
        timeout_seconds,
        max_rss_bytes,
        enforcement,
    )
    process = subprocess.Popen(
        list(spec.command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        start_new_session=True,
    )
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_thread = threading.Thread(
        target=_drain_bounded,
        args=(process.stdout, stdout_chunks),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_drain_bounded,
        args=(process.stderr, stderr_chunks),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    peak_rss = 0
    outcome: V3ScaleStatus | None = None
    reason: str | None = None
    deadline = started + timeout_seconds
    try:
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                break
            if rss_supported and max_rss_bytes is not None:
                observed = _process_tree_rss_bytes(process.pid)
                if observed is not None:
                    peak_rss = max(peak_rss, observed)
                    if observed > max_rss_bytes:
                        outcome = V3ScaleStatus.RESOURCE_EXHAUSTED
                        reason = "rss_budget_exceeded"
                        break
            if time.monotonic() >= deadline:
                outcome = V3ScaleStatus.TIMED_OUT
                reason = "deadline_exceeded"
                break
            time.sleep(_POLL_SECONDS)
    finally:
        if outcome is not None:
            _terminate_process_group(process)
        else:
            try:
                process.wait(timeout=_SHUTDOWN_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                outcome = V3ScaleStatus.FAILED
                reason = "worker_did_not_exit"
                _terminate_process_group(process)
        stdout_thread.join(timeout=_SHUTDOWN_GRACE_SECONDS)
        stderr_thread.join(timeout=_SHUTDOWN_GRACE_SECONDS)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        _write_stream(paths.stdout, stdout_chunks)
        _write_stream(paths.stderr, stderr_chunks)

    elapsed = time.monotonic() - started
    last_boundary = read_heartbeat_boundary(paths.heartbeat)
    if outcome is None and process.returncode != 0:
        outcome = V3ScaleStatus.FAILED
        reason = f"worker_exit_{process.returncode}"
    if outcome is None:
        if not paths.result.is_file():
            outcome = V3ScaleStatus.FAILED
            reason = "missing_terminal_result"
        else:
            try:
                measurement = read_measurement(paths.result)
            except V3ScaleMeasurementError:
                outcome = V3ScaleStatus.FAILED
                reason = "invalid_terminal_result"
            else:
                if (
                    measurement.workload_id != spec.workload.workload_id
                    or measurement.lane is not spec.workload.lane
                    or measurement.run_id != spec.workload.run_id.value
                ):
                    outcome = V3ScaleStatus.FAILED
                    reason = "terminal_result_identity_mismatch"
                else:
                    _LOG.info(
                        "v3_worker_complete workload_id=%s status=%s ticks=%s "
                        "elapsed_s=%.3f",
                        measurement.workload_id,
                        measurement.status.value,
                        measurement.completed_ticks,
                        elapsed,
                    )
                    return replace(
                        measurement,
                        peak_rss_bytes=(
                            peak_rss if peak_rss else measurement.peak_rss_bytes
                        ),
                        budget_rss_bytes=max_rss_bytes,
                        timeout_seconds=timeout_seconds,
                        rss_enforcement=enforcement,
                        command_identity=_command_identity(spec.command),
                        coverage_file=str(paths.coverage),
                    )
    assert outcome is not None
    completed = last_boundary + 1 if last_boundary >= 0 else 0
    measurement = incomplete_measurement(
        spec.workload,
        status=outcome,
        completed_ticks=completed,
        last_verified_boundary=max(0, last_boundary),
        elapsed_seconds=elapsed,
        exception_reason=reason or "worker_incomplete",
        peak_rss_bytes=peak_rss or None,
        budget_rss_bytes=max_rss_bytes,
        timeout_seconds=timeout_seconds,
        rss_enforcement=enforcement,
        command_identity=_command_identity(spec.command),
        coverage_file=str(paths.coverage),
    )
    _LOG.warning(
        "v3_worker_incomplete workload_id=%s status=%s reason=%s boundary=%s",
        spec.workload.workload_id,
        measurement.status.value,
        measurement.exception_reason,
        measurement.last_verified_boundary,
    )
    return measurement


def _drain_bounded(stream: IO[bytes] | None, chunks: list[bytes]) -> None:
    if stream is None:
        return
    total = 0
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            if total < _STREAM_CAPTURE_BYTES:
                remaining = _STREAM_CAPTURE_BYTES - total
                chunks.append(chunk[:remaining])
                total += min(len(chunk), remaining)
    except (OSError, ValueError):
        return


def _write_stream(path: Path, chunks: list[bytes]) -> None:
    payload = b"".join(chunks)
    path.write_bytes(payload)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=_SHUTDOWN_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=_SHUTDOWN_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        _LOG.warning("v3_worker_reap_failed pid=%s", process.pid)


def _rss_supported() -> bool:
    return Path("/proc/self/status").is_file()


def _process_tree_rss_bytes(root_pid: int) -> int | None:
    status = Path(f"/proc/{root_pid}/status")
    if not status.is_file():
        return None
    total_kb = 0
    seen: set[int] = set()
    pending = [root_pid]
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if len(seen) > 512:
            break
        total_kb += _rss_kb(pid)
        pending.extend(_child_pids(pid))
    return total_kb * 1024


def _rss_kb(pid: int) -> int:
    try:
        lines = Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    for line in lines:
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return 0


def _child_pids(pid: int) -> tuple[int, ...]:
    children: set[int] = set()
    task_root = Path(f"/proc/{pid}/task")
    try:
        tasks = tuple(task_root.iterdir())
    except OSError:
        return ()
    for task in tasks:
        try:
            text = (task / "children").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not text:
            continue
        for item in text.split():
            if item.isdigit():
                children.add(int(item))
    return tuple(sorted(children))


def _command_identity(command: tuple[str, ...]) -> str:
    basename = Path(command[0]).name
    digest = hashlib.sha256("\x00".join(command).encode("utf-8")).hexdigest()
    return f"{basename}#sha256:{digest}"


def module_command(module: str, *arguments: str) -> tuple[str, ...]:
    """Build a ``python -m`` command for this environment."""
    return (sys.executable, "-m", module, *arguments)


__all__ = [
    "COVERAGE_FILE_ENV",
    "HEARTBEAT_PATH_ENV",
    "OUTPUT_DIR_ENV",
    "RESULT_PATH_ENV",
    "WORKER_ENV",
    "WORKLOAD_ID_ENV",
    "V3WorkerSpec",
    "attempt_paths",
    "module_command",
    "read_heartbeat_boundary",
    "run_scale_worker",
    "worker_environment",
    "write_heartbeat",
]
