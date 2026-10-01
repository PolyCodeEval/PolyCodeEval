"""Shared helpers for running PolyCodeEval datasets in Docker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

DATASETS_ROOT = Path(os.environ.get("PCE_DATASETS_ROOT", str(Path(__file__).resolve().parents[1])))
DOCKER_ROOT = Path(__file__).resolve().parent
CACHE_ROOT = DOCKER_ROOT / ".cache"
TEXT_TESTDATA_EXTENSIONS = {
    ".go",
    ".json",
    ".log",
    ".md",
    ".sh",
    ".txt",
    ".txtar",
    ".yaml",
    ".yml",
}

UNIFIED_IMAGE = "polycodeeval/unified:all"
DEFAULT_DOCKER_PROXIES = [
    "http://172.19.135.130:5000",
    "http://host.docker.internal:7897",
]
PROXY_ENV_NAMES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)

CACHE_LAYOUT = {
    "python": ("pip", {"PIP_CACHE_DIR": "/cache/pip"}),
    "javascript": ("npm", {"npm_config_cache": "/cache/npm"}),
    "java": ("gradle", {"GRADLE_USER_HOME": "/cache/gradle"}),
    "go": ("go-build", {"GOCACHE": "/cache/go-build"}),
}

LANGUAGE_ENV = {
    "go": {"GOPROXY": "https://goproxy.cn,direct"},
    "python": {
        "PIP_INDEX_URL": "https://mirrors.aliyun.com/pypi/simple/",
        "PIP_TRUSTED_HOST": "mirrors.aliyun.com",
        "PIP_TIMEOUT": "300",
    },
    "javascript": {"npm_config_registry": "https://registry.npmmirror.com"},
    "java": {},
}

# Maps docker_image values from config/run_config to (language, version).
# Used to inject the correct env (JAVA_HOME, Node version) into the unified container.
VERSION_MAP: dict[str, tuple[str, str]] = {
    "openjdk:8-jdk-slim": ("java", "8"),
    "openjdk:11-jdk-slim": ("java", "11"),
    "openjdk:17-jdk-slim": ("java", "17"),
    "eclipse-temurin:8-jdk": ("java", "8"),
    "eclipse-temurin:17-jdk-jammy": ("java", "17"),
    "node:14-bullseye": ("javascript", "14"),
    "node:18-alpine": ("javascript", "18"),
    "node:20-alpine": ("javascript", "20"),
    "node:20": ("javascript", "20"),
    "node:22-alpine": ("javascript", "22"),
    "polycodeeval/node:20": ("javascript", "20"),
    "python:3.11-slim": ("python", "3.11"),
    "python:3.9-slim": ("python", "3.11"),
    "gcc:12": ("cpp", "12"),
    "golang:1.22-alpine": ("go", "1.23"),
    "golang:1.23-alpine": ("go", "1.23"),
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def discover_projects(language: str | None = None) -> list[Path]:
    projects: list[Path] = []
    datasets_dir = DATASETS_ROOT / "datasets"
    for config_path in datasets_dir.glob("*/**/config.json"):
        project_dir = config_path.parent
        if language and project_dir.parent.name != language:
            continue
        projects.append(project_dir)
    return sorted(projects)


def resolve_project_path(project: str) -> Path:
    candidate = Path(project)
    if candidate.is_absolute():
        return candidate
    resolved = DATASETS_ROOT / candidate
    if resolved.is_dir():
        return resolved
    return candidate


def load_project_config(project: str) -> tuple[Path, dict]:
    project_dir = resolve_project_path(project)
    config_path = project_dir / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"config.json not found for project: {project_dir}")
    return project_dir, load_json(config_path)


def resolve_version(docker_image: str) -> tuple[str, str]:
    """Return (language, version) for a docker_image value, or ('', '') if unknown."""
    return VERSION_MAP.get(docker_image, ("", ""))


def language_cache_mounts(language: str, project_dir: Path | None = None) -> tuple[list[tuple[Path, str]], dict[str, str]]:
    entry = CACHE_LAYOUT.get(language)
    if not entry:
        return [], {}
    cache_name, env = entry

    sub_dir = f"{cache_name}/{project_dir.name}" if project_dir else cache_name
    host_cache_dir = CACHE_ROOT / sub_dir
    host_cache_dir.mkdir(parents=True, exist_ok=True)
    return [(host_cache_dir, f"/cache/{cache_name}")], env


def prepare_testdata_mount(project_dir: Path) -> Path | None:
    source_testdata = project_dir / "tests" / "testdata"
    if not source_testdata.is_dir():
        return None

    relative_name = project_dir.name
    target_testdata = CACHE_ROOT / "go-testdata" / relative_name
    if target_testdata.exists():
        return target_testdata

    for source_path in source_testdata.rglob("*"):
        relative_path = source_path.relative_to(source_testdata)
        target_path = target_testdata / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix.lower() in TEXT_TESTDATA_EXTENSIONS:
            content = source_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            target_path.write_bytes(content)
        else:
            target_path.write_bytes(source_path.read_bytes())

    return target_testdata


JAVA_HOMES = {
    "8": "/usr/lib/jvm/java-8-openjdk",
    "11": "/usr/lib/jvm/java-11-openjdk",
    "17": "/usr/lib/jvm/java-17-openjdk",
}


def _find_reachable_proxy() -> str:
    """Try each candidate proxy and return the first one that accepts a TCP connection.

    Returns empty string if no proxy is reachable from the host.
    """
    import socket
    from urllib.parse import urlparse

    for url in DEFAULT_DOCKER_PROXIES:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 80
        try:
            sock = socket.create_connection((host, port), timeout=2)
            sock.close()
            return url
        except (OSError, socket.timeout):
            continue

    return ""


def proxy_env() -> dict[str, str]:
    """Return proxy env vars to inject into Docker containers.

    Preference order:
      1. Explicit env vars from the current host process.
      2. First reachable proxy from DEFAULT_DOCKER_PROXIES.
    """
    result: dict[str, str] = {}
    for name in PROXY_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            result[name] = value

    if not any(name in result for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")):
        proxy = _find_reachable_proxy()
        if proxy:
            result.setdefault("HTTP_PROXY", proxy)
            result.setdefault("HTTPS_PROXY", proxy)
            result.setdefault("http_proxy", proxy)
            result.setdefault("https_proxy", proxy)

    no_proxy = result.get("NO_PROXY") or result.get("no_proxy") or ""
    required = ["localhost", "127.0.0.1", "host.docker.internal"]
    items = [item.strip() for item in no_proxy.split(",") if item.strip()]
    for item in required:
        if item not in items:
            items.append(item)
    merged_no_proxy = ",".join(items)
    result["NO_PROXY"] = merged_no_proxy
    result["no_proxy"] = merged_no_proxy

    proxy_url = result.get("HTTP_PROXY") or result.get("http_proxy") or ""
    if proxy_url:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        host = parsed.hostname or ""
        port = parsed.port or 80
        java_proxy = f"-Dhttp.proxyHost={host} -Dhttp.proxyPort={port} -Dhttps.proxyHost={host} -Dhttps.proxyPort={port}"
        for key in ("JAVA_TOOL_OPTIONS", "GRADLE_OPTS", "MAVEN_OPTS"):
            existing = result.get(key, "")
            result[key] = f"{existing} {java_proxy}".strip()

    return result


def docker_command(
    project_dir: Path,
    script: str,
    *,
    language: str,
    docker_image: str = "",
    extra_args: Iterable[str] = (),
    cache_project_dir: Path | None = None,
) -> list[str]:
    cmd = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--dns",
        "223.5.5.5",
        "--sysctl",
        "net.ipv6.conf.all.disable_ipv6=1",
        "--sysctl",
        "net.ipv6.conf.default.disable_ipv6=1",
        "--add-host",
        "localhost:127.0.0.1",
        "--add-host",
        "host.docker.internal:host-gateway",
        "--add-host",
        "httpbin.org:52.54.122.173",
        "--add-host",
        "example.com:104.20.23.154",
        "--workdir",
        "/workspace",
        "--volume",
        f"{project_dir}:/workspace",
    ]
    cache_mounts, cache_env = language_cache_mounts(language, cache_project_dir or project_dir)
    for host_dir, container_dir in cache_mounts:
        cmd.extend(["--volume", f"{host_dir}:{container_dir}"])
    for key, value in cache_env.items():
        cmd.extend(["--env", f"{key}={value}"])
    for key, value in LANGUAGE_ENV.get(language, {}).items():
        cmd.extend(["--env", f"{key}={value}"])
    for key, value in proxy_env().items():
        cmd.extend(["--env", f"{key}={value}"])

    # Inject version-specific env vars derived from docker_image
    if docker_image:
        _, version = VERSION_MAP.get(docker_image, ("", ""))
        if language == "java" and version in JAVA_HOMES:
            java_home = JAVA_HOMES[version]
            cmd.extend(["--env", f"JAVA_HOME={java_home}"])
        elif language == "javascript" and version:
            # Wrap script to use the correct Node version via n
            script = f"n exec {version} sh -c {json.dumps(script)}"

    project_testdata = project_dir / "tests" / "testdata"
    if project_testdata.is_dir():
        mounted_testdata = prepare_testdata_mount(project_dir)
        if mounted_testdata is not None:
            cmd.extend(["--volume", f"{mounted_testdata}:/workspace/src/testdata"])
    cmd.extend(list(extra_args))

    # For Java: inject proxy into settings.xml and gradle.properties at runtime
    if language == "java":
        penv = proxy_env()
        proxy_url = penv.get("HTTP_PROXY") or penv.get("http_proxy") or ""
        if proxy_url:
            from urllib.parse import urlparse
            parsed = urlparse(proxy_url)
            phost = parsed.hostname or ""
            pport = parsed.port or 80
            java_proxy_setup = (
                f'mkdir -p /root/.m2 /root/.gradle && '
                f'cat > /root/.m2/settings.xml << \'XMLEOF\'\n'
                f'<?xml version="1.0"?>\n'
                f'<settings><mirrors><mirror><id>aliyun</id><mirrorOf>*</mirrorOf>'
                f'<url>https://maven.aliyun.com/repository/public</url></mirror></mirrors>'
                f'<proxies><proxy><id>p1</id><active>true</active><protocol>http</protocol>'
                f'<host>{phost}</host><port>{pport}</port></proxy>'
                f'<proxy><id>p2</id><active>true</active><protocol>https</protocol>'
                f'<host>{phost}</host><port>{pport}</port></proxy></proxies></settings>\n'
                f'XMLEOF\n'
                f'printf "systemProp.http.proxyHost={phost}\\n'
                f'systemProp.http.proxyPort={pport}\\n'
                f'systemProp.https.proxyHost={phost}\\n'
                f'systemProp.https.proxyPort={pport}\\n" > /root/.gradle/gradle.properties && '
            )
            script = java_proxy_setup + script

    cmd.extend([UNIFIED_IMAGE, "sh", "-c", script])
    return cmd


def build_script(install_command: str, test_command: str) -> str:
    parts = []
    if install_command.strip():
        parts.append(f"cd /workspace && {{ {install_command.strip()}; }}")
    if test_command.strip():
        parts.append(f"cd /workspace && {{ {test_command.strip()}; }}")
    if not parts:
        raise ValueError("config.json must provide at least a test_command")
    return "set -eu; " + " && ".join(parts)


def build_combined_script(
    install_command: str,
    test_command: str,
    *,
    run_whitebox: bool = True,
    run_blackbox: bool = True,
) -> str:
    """Build a script that runs install, then whitebox tests, then blackbox tests.

    Whitebox runs first to avoid Go blackbox tests copying *_test.go into src
    before the whitebox suite runs.
    """
    parts = []
    if install_command.strip():
        parts.append(f"cd /workspace && {{ {install_command.strip()}; }}")
    if run_whitebox and test_command.strip():
        parts.append(f"cd /workspace && {{ {test_command.strip()}; }}")
    if run_blackbox:
        parts.append(
            "if [ -f /workspace/blackbox_tests/run_tests.sh ]; then "
            "sh /workspace/blackbox_tests/run_tests.sh; fi"
        )
    if not parts:
        raise ValueError("config.json must provide at least a test_command")
    return "set -eu; " + " && ".join(parts)


def run_batch(
    projects: list[dict],
    *,
    extra_mounts: list[tuple[Path, str]] = (),
    timeout: int = 7200,
) -> list[dict]:
    """Run multiple projects in a single Docker container.

    Each entry in `projects` must have: name, language, version, workspace (host path),
    script, timeout, task_id.  Results are returned as a list of dicts.
    """
    batch_tmp = Path(tempfile.mkdtemp(prefix="pce_batch_"))
    results_dir = batch_tmp / "results"
    results_dir.mkdir()

    # Mount each workspace directly into /workspaces/<name>; no symlinks needed
    manifest_projects = []
    workspace_mounts: list[str] = []
    for p in projects:
        ws_name = p["name"]
        host_ws = Path(p["workspace"])
        workspace_mounts.append(f"{host_ws}:/workspaces/{ws_name}")
        manifest_projects.append({
            **p,
            "workspace": f"/workspaces/{ws_name}",
        })

    manifest_path = batch_tmp / "manifest.json"
    manifest_path.write_text(json.dumps({"projects": manifest_projects}, indent=2))

    cmd = [
        "docker", "run", "--rm", "--init",
        "--sysctl", "net.ipv6.conf.all.disable_ipv6=1",
        "--sysctl", "net.ipv6.conf.default.disable_ipv6=1",
        "--add-host", "localhost:127.0.0.1",
        "--workdir", "/entrypoint",
        "--volume", f"{manifest_path}:/manifest/projects.json:ro",
        "--volume", f"{results_dir}:/results",
    ]
    for ws_mount in workspace_mounts:
        cmd.extend(["--volume", ws_mount])
    for host_path, container_path in extra_mounts:
        cmd.extend(["--volume", f"{host_path}:{container_path}"])
    cmd.extend([UNIFIED_IMAGE, "python3", "/entrypoint/run_batch.py"])

    proc = subprocess.run(cmd, text=True, timeout=timeout)

    results_file = results_dir / "results.json"
    if results_file.exists():
        return json.loads(results_file.read_text())["results"]

    # Container crashed — mark all as failed (stdout/stderr were streamed to terminal)
    return [
        {
            "name": p["name"],
            "task_id": p.get("task_id", p["name"]),
            "language": p["language"],
            "passed": False,
            "exit_code": proc.returncode,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": f"Container exited with code {proc.returncode} (output streamed to terminal)",
        }
        for p in projects
    ]
