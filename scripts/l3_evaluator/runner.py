"""Runner — executes project tests in Docker using the unified image."""

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
    build_combined_script,
    build_script,
    docker_command,
    prepare_testdata_mount,
    proxy_env,
    resolve_version,
)

from .workspace import Workspace  # noqa: E402


def run(workspace: Workspace, task_dir: Path, *, timeout: int = 600, test_mode: str = "both") -> dict:
    run_config = workspace.run_config
    language = task_dir.parents[2].name

    if test_mode == "whitebox":
        script = build_script(run_config.get("install_command", ""), run_config["test_command"])
    else:
        script = build_combined_script(
            run_config.get("install_command", ""),
            run_config["test_command"],
            run_whitebox=(test_mode != "blackbox"),
            run_blackbox=(test_mode != "whitebox"),
        )
    cmd = docker_command(workspace.tmp_dir, script, language=language, docker_image=run_config.get("docker_image", ""))

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = f"Docker run timed out after {timeout}s"

    return {
        "passed": exit_code == 0,
        "exit_code": exit_code,
        "duration_seconds": round(time.monotonic() - start, 2),
        "stdout": stdout[-8000:],
        "stderr": stderr[-4000:],
    }


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


def _pre_test_cleanup(language: str) -> str:
    # Remove stale build artifacts and caches from previous task runs in the
    # shared project container. This keeps each task run equivalent to a fresh
    # single-task workspace build.
    if language == "cpp":
        return (
            "rm -rf /workspace/src/obj /workspace/src/run_tests /workspace/src/graph; "
            "find /workspace/src /workspace/tests "
            "-type f \\( -name '*.gcda' -o -name '*.gcno' -o -name '*.o' \\) "
            "-delete 2>/dev/null || true"
        )
    elif language == "java":
        # Remove Gradle build cache and daemon state to prevent UP-TO-DATE tasks
        return (
            "rm -rf /root/.gradle/caches /root/.gradle/daemon /workspace/src/.gradle /workspace/src/build"
        )
    return ""


class ProjectContainer:
    """Long-running Docker container shared by all tasks in a single project."""

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
        self._using_preloaded_project = False

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

    def start(self, *, timeout: int = 600) -> None:
        src_dir = (self.project_dir / "src").resolve()
        tests_dir = self.project_dir / "tests"
        project_rel = f"{self.language}/{self.project_dir.name}"
        preloaded_root = f"/opt/pce-projects/{project_rel}"

        image = self._docker_image or UNIFIED_IMAGE

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
            sub_dir = f"{cache_name}/{self.project_dir.name}"
            host_cache_dir = CACHE_ROOT / sub_dir
            host_cache_dir.mkdir(parents=True, exist_ok=True)
            create_cmd.extend(["--volume", f"{host_cache_dir}:/cache/{cache_name}"])
            for key, value in cache_env.items():
                create_cmd.extend(["--env", f"{key}={value}"])

        for key, value in LANGUAGE_ENV.get(self.language, {}).items():
            create_cmd.extend(["--env", f"{key}={value}"])
        for key, value in proxy_env().items():
            create_cmd.extend(["--env", f"{key}={value}"])

        docker_image = self.run_config.get("docker_image", "")
        _, version = resolve_version(docker_image)
        if self.language == "java" and version in JAVA_HOMES:
            create_cmd.extend(["--env", f"JAVA_HOME={JAVA_HOMES[version]}"])

        if self.language == "go" and tests_dir.is_dir():
            mounted_testdata = prepare_testdata_mount(self.project_dir)
            if mounted_testdata is not None:
                create_cmd.extend(["--volume", f"{mounted_testdata}:/workspace/src/testdata"])

        create_cmd.extend([image, "sleep", "infinity"])

        proc = subprocess.run(
            create_cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to create container: {proc.stderr}")
        self._container_id = proc.stdout.strip()[:12]

        if self._docker_image:
            preload = self._docker_exec(
                f"if [ -d {preloaded_root} ]; then cp -a {preloaded_root}/. /workspace/ && echo PRELOADED; fi",
                timeout=timeout,
            )
            self._using_preloaded_project = "PRELOADED" in preload["stdout"]

        self._docker_cp_in(src_dir, "/workspace/src", contents_only=True)
        if tests_dir.is_dir():
            self._docker_cp_in(tests_dir, "/workspace/tests", contents_only=True)
        blackbox_dir = self.project_dir / "blackbox_tests"
        if blackbox_dir.is_dir():
            self._docker_cp_in(blackbox_dir, "/workspace/blackbox_tests", contents_only=True)

        # Skip install_command only when the custom image already contains a
        # preloaded project workspace under /opt/pce-projects/<lang>/<project>.
        if not self._using_preloaded_project:
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
            self._tests_backup_dir = Path(tempfile.mkdtemp(prefix="pce_tests_bak_"))

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

        tmp_original = Path(tempfile.mktemp(prefix="pce_restore_"))
        try:
            tmp_original.write_bytes(original_bytes)
            self._docker_cp_file_in(tmp_original, container_path)
        finally:
            tmp_original.unlink(missing_ok=True)

        self._restore_tests_targets()

        # Go blackbox tests copy *_test.go into /workspace/src; clean up to avoid
        # contaminating subsequent tasks in the same container.
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
                subprocess.run(
                    ["docker", "rm", "-f", self._container_id],
                    capture_output=True, timeout=120,
                )
            except (subprocess.TimeoutExpired, Exception):
                try:
                    subprocess.run(
                        ["docker", "kill", self._container_id],
                        capture_output=True, timeout=30,
                    )
                except Exception:
                    pass
            self._container_id = None
        if self._tests_backup_dir:
            shutil.rmtree(self._tests_backup_dir, ignore_errors=True)
            self._tests_backup_dir = None

    def _docker_cp_in(self, host_path: Path, container_path: str, *, contents_only: bool = False) -> None:
        src = f"{host_path}/." if contents_only else str(host_path)
        self._docker_exec(f"mkdir -p {container_path}", timeout=10)
        subprocess.run(
            ["docker", "cp", src, f"{self._container_id}:{container_path}/"],
            capture_output=True, check=True, timeout=600,
        )

    def _docker_cp_file_in(self, host_file: Path, container_path: str) -> None:
        parent = str(Path(container_path).parent)
        self._docker_exec(f"mkdir -p {parent}", timeout=10)
        subprocess.run(
            ["docker", "cp", str(host_file), f"{self._container_id}:{container_path}"],
            capture_output=True, check=True, timeout=60,
        )

    def _docker_cp_out(self, container_path: str, host_path: Path) -> bool:
        proc = subprocess.run(
            ["docker", "cp", f"{self._container_id}:{container_path}", str(host_path)],
            capture_output=True, timeout=60,
        )
        return proc.returncode == 0

    def _docker_exec(self, script: str, *, timeout: int = 600) -> dict:
        cmd = ["docker", "exec", self._container_id, "sh", "-c", script]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace",
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired:
            exit_code = -1
            stdout = ""
            stderr = f"Docker exec timed out after {timeout}s"
        return {
            "passed": exit_code == 0,
            "exit_code": exit_code,
            "duration_seconds": round(time.monotonic() - start, 2),
            "stdout": stdout[-8000:],
            "stderr": stderr[-4000:],
        }

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
