"""Runner — long-running Docker container for L2 file-level evaluation.

Architecture mirrors L3: one container per project, shared across all tasks.
install_command runs once at container start; each task only backfills the
target file and re-runs test_command.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_DOCKER_DIR = str(Path(__file__).resolve().parents[2] / "docker")
if _DOCKER_DIR not in sys.path:
    sys.path.insert(0, _DOCKER_DIR)

from runner_lib import (  # noqa: E402
    CACHE_LAYOUT,
    CACHE_ROOT,
    JAVA_HOMES,
    LANGUAGE_ENV,
    UNIFIED_IMAGE,
    prepare_testdata_mount,
    proxy_env,
    resolve_version,
)

from .workspace import Workspace  # noqa: E402


def _pre_test_cleanup(language: str) -> str:
    if language == "cpp":
        return (
            "rm -rf /workspace/src/obj /workspace/src/run_tests /workspace/src/graph; "
            "find /workspace/src /workspace/tests "
            "-type f \\( -name '*.gcda' -o -name '*.gcno' -o -name '*.o' \\) "
            "-delete 2>/dev/null || true"
        )
    elif language == "java":
        return (
            "rm -rf /root/.gradle/caches /root/.gradle/daemon "
            "/workspace/src/.gradle /workspace/src/build 2>/dev/null || true"
        )
    return ""


def _detect_tests_write_targets(install_cmd: str, test_cmd: str) -> list[str]:
    combined = install_cmd + " && " + test_cmd
    targets: list[str] = []
    for m in re.finditer(r'cp\s+(?:-r\s+)?\.\.\/tests\/?\*?\s+(\S+)', combined):
        targets.append(m.group(1).rstrip("/"))
    for m in re.finditer(r'cat\s*>\s*(tests/\S+)', combined):
        targets.append(m.group(1))
    for m in re.finditer(r'cp\s+\S+\s+(tests/\S+)', combined):
        targets.append(m.group(1))
    return targets


class ProjectContainer:
    """Long-running Docker container shared by all L2 tasks in a single project."""

    def __init__(
        self,
        project_dir: Path,
        run_config: dict,
        language: str,
        *,
        test_mode: str = "both",
        docker_image: str = "",
    ):
        self.project_dir = project_dir
        self.run_config = run_config
        self.language = language
        self._test_mode = test_mode
        self._docker_image = docker_image
        self._container_id: str | None = None
        self._tests_write_targets: list[str] = []
        self._tests_backup_dir: Path | None = None

    def _runtime_script(self, script: str) -> str:
        docker_image = self.run_config.get("docker_image", "")
        _, version = resolve_version(docker_image)
        if self.language == "javascript" and version:
            return f"n exec {version} sh -c {json.dumps(script)}"
        return script

    def _inject_java_proxy(self) -> None:
        penv = proxy_env()
        proxy_url = penv.get("HTTP_PROXY") or penv.get("http_proxy") or ""
        if not proxy_url:
            return
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        phost = parsed.hostname or ""
        pport = parsed.port or 80
        script = (
            f'mkdir -p /root/.m2 /root/.gradle && '
            f'printf \'<?xml version="1.0"?>\\n'
            f'<settings><mirrors><mirror><id>aliyun</id><mirrorOf>*</mirrorOf>'
            f'<url>https://maven.aliyun.com/repository/public</url></mirror></mirrors>'
            f'<proxies><proxy><id>p1</id><active>true</active><protocol>http</protocol>'
            f'<host>{phost}</host><port>{pport}</port></proxy>'
            f'<proxy><id>p2</id><active>true</active><protocol>https</protocol>'
            f'<host>{phost}</host><port>{pport}</port></proxy></proxies></settings>\\n\''
            f' > /root/.m2/settings.xml && '
            f'printf \'systemProp.http.proxyHost={phost}\\n'
            f'systemProp.http.proxyPort={pport}\\n'
            f'systemProp.https.proxyHost={phost}\\n'
            f'systemProp.https.proxyPort={pport}\\n\''
            f' > /root/.gradle/gradle.properties'
        )
        self._docker_exec(script, timeout=30)

    def start(self, src_dir: Path, tests_dir: Path | None, *, timeout: int = 900) -> None:
        """Start the container, copy source files, run install_command."""
        image = UNIFIED_IMAGE

        create_cmd = [
            "docker", "run", "-d",
            "--init",
            "--dns", "223.5.5.5",
            "--sysctl", "net.ipv6.conf.all.disable_ipv6=1",
            "--sysctl", "net.ipv6.conf.default.disable_ipv6=1",
            "--add-host", "localhost:127.0.0.1",
            "--add-host", "host.docker.internal:host-gateway",
            "--add-host", "httpbin.org:52.54.122.173",
            "--add-host", "example.com:104.20.23.154",
            "--workdir", "/workspace",
        ]

        entry = CACHE_LAYOUT.get(self.language)
        if entry:
            cache_name, cache_env = entry
            host_cache = CACHE_ROOT / cache_name / self.project_dir.name
            host_cache.mkdir(parents=True, exist_ok=True)
            create_cmd.extend(["--volume", f"{host_cache}:/cache/{cache_name}"])
            for k, v in cache_env.items():
                create_cmd.extend(["--env", f"{k}={v}"])

        for k, v in LANGUAGE_ENV.get(self.language, {}).items():
            create_cmd.extend(["--env", f"{k}={v}"])
        for k, v in proxy_env().items():
            create_cmd.extend(["--env", f"{k}={v}"])

        docker_image = self.run_config.get("docker_image", "")
        _, version = resolve_version(docker_image)
        if self.language == "java" and version in JAVA_HOMES:
            create_cmd.extend(["--env", f"JAVA_HOME={JAVA_HOMES[version]}"])

        if self.language == "go" and tests_dir and tests_dir.is_dir():
            mounted_testdata = prepare_testdata_mount(self.project_dir)
            if mounted_testdata is not None:
                create_cmd.extend(["--volume", f"{mounted_testdata}:/workspace/src/testdata"])

        create_cmd.extend([image, "sleep", "infinity"])

        proc = subprocess.run(create_cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to start container: {proc.stderr}")
        self._container_id = proc.stdout.strip()[:12]

        self._docker_cp_in(src_dir, "/workspace/src", contents_only=True)
        if tests_dir and tests_dir.is_dir():
            self._docker_cp_in(tests_dir, "/workspace/tests", contents_only=True)
        blackbox_dir = self.project_dir / "blackbox_tests"
        if blackbox_dir.is_dir():
            self._docker_cp_in(blackbox_dir, "/workspace/blackbox_tests", contents_only=True)

        if self.language == "java":
            self._inject_java_proxy()

        install_cmd = self.run_config.get("install_command", "").strip()
        if install_cmd:
            script = self._runtime_script(f"set -eu; cd /workspace && {{ {install_cmd}; }}")
            result = self._docker_exec(script, timeout=timeout)
            if result["exit_code"] != 0:
                raise RuntimeError(
                    f"install_command failed (exit {result['exit_code']}): "
                    f"{result['stderr'][-2000:]}"
                )

        self._tests_write_targets = _detect_tests_write_targets(
            self.run_config.get("install_command", ""),
            self.run_config["test_command"],
        )
        if self._tests_write_targets:
            self._tests_backup_dir = Path(tempfile.mkdtemp(prefix="pce_l2_tests_bak_"))

    def exec_task(
        self,
        backfilled_file: Path,
        container_rel_path: str,
        original_bytes: bytes,
        *,
        timeout: int = 600,
    ) -> dict:
        container_path = f"/workspace/src/{container_rel_path}"

        self._backup_tests_targets()
        self._docker_cp_file_in(backfilled_file, container_path)

        test_cmd = self.run_config["test_command"].strip()
        # Inject -v for Go so the test parser can collect individual test results
        if self.language == "go" and "go test" in test_cmd and "-v" not in test_cmd:
            test_cmd = re.sub(r"\bgo test\b", "go test -v", test_cmd)

        cleanup_cmd = _pre_test_cleanup(self.language)
        prefix = f"{cleanup_cmd}; " if cleanup_cmd else ""

        if self._test_mode == "both":
            script = (
                f"set -eu; {prefix}cd /workspace && {{ {test_cmd}; }} && "
                "if [ -f /workspace/blackbox_tests/run_tests.sh ]; then "
                "sh /workspace/blackbox_tests/run_tests.sh; fi"
            )
        elif self._test_mode == "blackbox":
            script = (
                "set -eu; if [ -f /workspace/blackbox_tests/run_tests.sh ]; then "
                "sh /workspace/blackbox_tests/run_tests.sh; fi"
            )
        else:
            script = f"set -eu; {prefix}cd /workspace && {{ {test_cmd}; }}"

        result = self._docker_exec(self._runtime_script(script), timeout=timeout)

        tmp_original = Path(tempfile.mktemp(prefix="pce_l2_restore_"))
        try:
            tmp_original.write_bytes(original_bytes)
            self._docker_cp_file_in(tmp_original, container_path)
        finally:
            tmp_original.unlink(missing_ok=True)

        self._restore_tests_targets()

        if self._test_mode in ("both", "blackbox") and self.language == "go":
            cleanup = (
                "cd /workspace/src && "
                "for f in /workspace/blackbox_tests/*_test.go; do "
                '[ -f "$f" ] && rm -f "$(basename $f)"; done'
            )
            self._docker_exec(cleanup, timeout=10)

        return result

    def stop(self) -> None:
        if self._container_id:
            try:
                subprocess.run(["docker", "rm", "-f", self._container_id],
                               capture_output=True, timeout=120)
            except (subprocess.TimeoutExpired, Exception):
                try:
                    subprocess.run(["docker", "kill", self._container_id],
                                   capture_output=True, timeout=30)
                except Exception:
                    pass
            self._container_id = None
        if self._tests_backup_dir:
            shutil.rmtree(self._tests_backup_dir, ignore_errors=True)
            self._tests_backup_dir = None

    # ------------------------------------------------------------------
    # Docker helpers
    # ------------------------------------------------------------------

    def _docker_exec(self, script: str, *, timeout: int = 600) -> dict:
        cmd = ["docker", "exec", self._container_id, "sh", "-c", script]
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout, encoding="utf-8", errors="replace")
            exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            exit_code, stdout = -1, ""
            stderr = f"Docker exec timed out after {timeout}s"
        full = stdout
        saved = full[:8000] + "\n...\n" + full[-24000:] if len(full) > 32000 else full
        return {
            "passed": exit_code == 0,
            "exit_code": exit_code,
            "duration_seconds": round(time.monotonic() - start, 2),
            "stdout": saved,
            "stderr": stderr[-8000:],
        }

    def _docker_cp_in(self, host_path: Path, container_path: str,
                      *, contents_only: bool = False) -> None:
        src = f"{host_path}/." if contents_only else str(host_path)
        self._docker_exec(f"mkdir -p {container_path}", timeout=10)
        subprocess.run(["docker", "cp", src, f"{self._container_id}:{container_path}/"],
                       capture_output=True, check=True, timeout=120)

    def _docker_cp_file_in(self, host_file: Path, container_path: str) -> None:
        parent = str(Path(container_path).parent)
        self._docker_exec(f"mkdir -p {parent}", timeout=10)
        subprocess.run(["docker", "cp", str(host_file),
                        f"{self._container_id}:{container_path}"],
                       capture_output=True, check=True, timeout=60)

    def _docker_cp_out(self, container_path: str, host_path: Path) -> bool:
        proc = subprocess.run(
            ["docker", "cp", f"{self._container_id}:{container_path}", str(host_path)],
            capture_output=True, timeout=60,
        )
        return proc.returncode == 0

    def _backup_tests_targets(self) -> None:
        if not self._tests_write_targets or not self._tests_backup_dir:
            return
        for target in self._tests_write_targets:
            container_path = target if target.startswith("/") else f"/workspace/{target}"
            local_dest = self._tests_backup_dir / target.replace("/", "_")
            self._docker_cp_out(container_path, local_dest)

    def _restore_tests_targets(self) -> None:
        if not self._tests_write_targets or not self._tests_backup_dir:
            return
        for target in self._tests_write_targets:
            container_path = target if target.startswith("/") else f"/workspace/{target}"
            local_src = self._tests_backup_dir / target.replace("/", "_")
            if local_src.exists():
                self._docker_cp_file_in(local_src, container_path)
