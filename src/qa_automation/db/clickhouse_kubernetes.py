from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
from types import TracebackType
from typing import Any, cast

from pydantic import SecretStr

from qa_automation.config import Settings
from qa_automation.db.kubernetes import KubernetesDatabaseError


class KubectlClickHouseTunnel:
    """Expose dev ClickHouse HTTP on loopback without persisting cluster credentials."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._process: subprocess.Popen[str] | None = None
        self._resource_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    def __enter__(self) -> Settings:
        self._validate_configuration()
        self._validate_current_context()
        local_port = self._settings.stat_clickhouse_kube_local_port
        if self._port_is_open(local_port):
            raise KubernetesDatabaseError(
                f"local ClickHouse HTTP port {local_port} is already in use"
            )

        environment = self._deployment_environment()
        required = ("CLICKHOUSE_DB", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
        missing = [name for name in required if not environment.get(name)]
        if missing:
            raise KubernetesDatabaseError(
                "stat-dispatcher does not expose required ClickHouse configuration: "
                + ", ".join(missing)
            )

        self._start_port_forward()
        try:
            self._wait_until_ready()
        except BaseException:
            self.close()
            raise

        return self._settings.model_copy(
            update={
                "stat_clickhouse_host": "127.0.0.1",
                "stat_clickhouse_http_port": local_port,
                "stat_clickhouse_database": environment["CLICKHOUSE_DB"],
                "stat_clickhouse_user": environment["CLICKHOUSE_USER"],
                "stat_clickhouse_password": SecretStr(environment["CLICKHOUSE_PASSWORD"]),
                "stat_clickhouse_secure": False,
            }
        )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        finally:
            if process.stderr is not None:
                process.stderr.close()

    def _validate_configuration(self) -> None:
        missing = self._settings.missing_stat_clickhouse_kubernetes_configuration()
        if missing:
            raise KubernetesDatabaseError(
                f"missing Stat ClickHouse Kubernetes configuration: {', '.join(missing)}"
            )

    def _validate_current_context(self) -> None:
        expected = self._required(self._settings.stat_clickhouse_kube_context)
        actual = self._run_kubectl("config", "current-context").stdout.strip()
        if actual != expected:
            raise KubernetesDatabaseError(
                "kubectl context does not match the configured context; refusing ClickHouse tunnel"
            )

    def _deployment_environment(self) -> dict[str, str]:
        namespace = self._required(self._settings.stat_clickhouse_kube_deployment_namespace)
        deployment = self._required(self._settings.stat_clickhouse_kube_deployment)
        payload = self._get_resource("deployment", deployment, namespace)
        containers = cast(list[dict[str, Any]], payload["spec"]["template"]["spec"]["containers"])
        expected_container = self._required(self._settings.stat_clickhouse_kube_container)
        container = next(
            (item for item in containers if item.get("name") == expected_container), None
        )
        if container is None:
            raise KubernetesDatabaseError(
                "configured container was not found in the configured deployment"
            )

        values: dict[str, str] = {}
        entries = cast(list[dict[str, Any]], container.get("env", []))
        for entry in entries:
            name = str(entry.get("name", ""))
            if name not in {"CLICKHOUSE_DB", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD"}:
                continue
            values[name] = self._resolve_environment_value(entry, namespace)
        return values

    def _resolve_environment_value(self, entry: dict[str, Any], namespace: str) -> str:
        if entry.get("value") is not None:
            return str(entry["value"])

        value_from = cast(dict[str, Any], entry.get("valueFrom", {}))
        secret_ref = cast(dict[str, Any] | None, value_from.get("secretKeyRef"))
        if secret_ref:
            secret = self._get_resource("secret", str(secret_ref["name"]), namespace)
            data = cast(dict[str, str], secret.get("data", {}))
            encoded = data.get(str(secret_ref["key"]))
            if encoded is None:
                raise KubernetesDatabaseError("referenced ClickHouse secret key was not found")
            return base64.b64decode(encoded, validate=True).decode("utf-8")

        config_map_ref = cast(dict[str, Any] | None, value_from.get("configMapKeyRef"))
        if config_map_ref:
            config_map = self._get_resource("configmap", str(config_map_ref["name"]), namespace)
            data = cast(dict[str, str], config_map.get("data", {}))
            value = data.get(str(config_map_ref["key"]))
            if value is None:
                raise KubernetesDatabaseError("referenced ClickHouse ConfigMap key was not found")
            return value

        raise KubernetesDatabaseError("unsupported ClickHouse environment value source")

    def _get_resource(self, kind: str, name: str, namespace: str) -> dict[str, Any]:
        cache_key = (kind, name, namespace)
        cached = self._resource_cache.get(cache_key)
        if cached is not None:
            return cached
        result = self._run_kubectl("get", kind, name, "--namespace", namespace, "--output", "json")
        try:
            payload = cast(dict[str, Any], json.loads(result.stdout))
        except json.JSONDecodeError as error:
            raise KubernetesDatabaseError(
                f"kubectl returned invalid JSON for resource kind {kind}"
            ) from error
        self._resource_cache[cache_key] = payload
        return payload

    def _start_port_forward(self) -> None:
        context = self._required(self._settings.stat_clickhouse_kube_context)
        namespace = self._required(self._settings.stat_clickhouse_kube_service_namespace)
        service = self._required(self._settings.stat_clickhouse_kube_service)
        command = [
            self._settings.stat_clickhouse_kubectl_path,
            f"--context={context}",
            "port-forward",
            "--namespace",
            namespace,
            f"service/{service}",
            (
                f"{self._settings.stat_clickhouse_kube_local_port}:"
                f"{self._settings.stat_clickhouse_kube_remote_port}"
            ),
            "--address=127.0.0.1",
        ]
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=self._creation_flags(),
            )
        except OSError:
            raise KubernetesDatabaseError("could not start kubectl port-forward") from None

    def _wait_until_ready(self) -> None:
        process = self._process
        if process is None:
            raise KubernetesDatabaseError("kubectl port-forward process was not started")
        deadline = (
            time.monotonic() + self._settings.stat_clickhouse_kube_start_timeout.total_seconds()
        )
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                raise KubernetesDatabaseError(
                    f"kubectl port-forward exited with code {return_code}"
                )
            if self._port_is_open(self._settings.stat_clickhouse_kube_local_port):
                return
            time.sleep(0.1)
        raise KubernetesDatabaseError("kubectl port-forward did not become ready before timeout")

    def _run_kubectl(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                [self._settings.stat_clickhouse_kubectl_path, *arguments],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._settings.stat_clickhouse_kube_start_timeout.total_seconds(),
                creationflags=self._creation_flags(),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise KubernetesDatabaseError("kubectl command failed to start") from None
        if result.returncode != 0:
            raise KubernetesDatabaseError(f"kubectl command failed with code {result.returncode}")
        return result

    @staticmethod
    def _port_is_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            return False

    @staticmethod
    def _creation_flags() -> int:
        return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    @staticmethod
    def _required(value: str | None) -> str:
        if value is None:
            raise KubernetesDatabaseError("required Kubernetes setting is missing")
        return value
