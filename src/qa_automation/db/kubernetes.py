from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Literal, cast

from pydantic import SecretStr

from qa_automation.config import Settings


class KubernetesDatabaseError(RuntimeError):
    """Raised when the Kubernetes-backed database connection cannot be prepared safely."""


DatabaseService = Literal["promocodes", "balance"]


@dataclass(frozen=True)
class _TunnelConfiguration:
    database_service: DatabaseService
    kubectl_path: str
    context: str | None
    namespace: str | None
    service: str | None
    deployment: str | None
    container: str | None
    local_port: int
    remote_port: int
    start_timeout_seconds: float


class KubectlPostgresTunnel:
    """Expose a cluster-internal PostgreSQL service on loopback for one test session."""

    def __init__(
        self,
        settings: Settings,
        *,
        database_service: DatabaseService = "promocodes",
    ) -> None:
        self._settings = settings
        self._config = self._build_configuration(settings, database_service)
        self._process: subprocess.Popen[str] | None = None
        self._resource_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def __enter__(self) -> Settings:
        self._validate_configuration()
        self._validate_current_context()

        local_port = self._config.local_port
        if self._port_is_open(local_port):
            raise KubernetesDatabaseError(
                f"local PostgreSQL port {local_port} is already in use; choose another port"
            )

        environment = self._deployment_environment()
        required_variables = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASS")
        missing_variables = [name for name in required_variables if not environment.get(name)]
        if missing_variables:
            raise KubernetesDatabaseError(
                "deployment does not expose required PostgreSQL configuration: "
                + ", ".join(missing_variables)
            )

        self._start_port_forward()
        try:
            self._wait_until_ready()
        except BaseException:
            self.close()
            raise

        connection = {
            "host": "127.0.0.1",
            "port": local_port,
            "name": environment["POSTGRES_DB"],
            "user": environment["POSTGRES_USER"],
            "password": SecretStr(environment["POSTGRES_PASS"]),
            "sslmode": "disable",
        }
        prefix = f"{self._config.database_service}_db_"
        return self._settings.model_copy(
            update={f"{prefix}{field}": value for field, value in connection.items()}
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
        required = {
            "CONTEXT": self._config.context,
            "NAMESPACE": self._config.namespace,
            "SERVICE": self._config.service,
            "DEPLOYMENT": self._config.deployment,
            "CONTAINER": self._config.container,
        }
        prefix = self._config.database_service.upper()
        missing = [f"{prefix}_DB_KUBE_{name}" for name, value in required.items() if value is None]
        if missing:
            raise KubernetesDatabaseError(
                f"missing Kubernetes database configuration: {', '.join(missing)}"
            )

    def _validate_current_context(self) -> None:
        expected = self._required_setting(self._config.context)
        result = self._run_kubectl("config", "current-context")
        actual = result.stdout.strip()
        if actual != expected:
            raise KubernetesDatabaseError(
                "kubectl context does not match the configured context; refusing database tunnel"
            )

    def _deployment_environment(self) -> dict[str, str]:
        deployment_name = self._required_setting(self._config.deployment)
        payload = self._get_resource("deployment", deployment_name)
        spec = cast(dict[str, Any], payload["spec"])
        template = cast(dict[str, Any], spec["template"])
        pod_spec = cast(dict[str, Any], template["spec"])
        containers = cast(list[dict[str, Any]], pod_spec["containers"])
        expected_container = self._required_setting(self._config.container)
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
            if name not in {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASS"}:
                continue
            values[name] = self._resolve_environment_value(entry)
        return values

    def _resolve_environment_value(self, entry: dict[str, Any]) -> str:
        if entry.get("value") is not None:
            return str(entry["value"])

        value_from = cast(dict[str, Any], entry.get("valueFrom", {}))
        secret_ref = cast(dict[str, Any] | None, value_from.get("secretKeyRef"))
        if secret_ref:
            secret = self._get_resource("secret", str(secret_ref["name"]))
            data = cast(dict[str, str], secret.get("data", {}))
            encoded = data.get(str(secret_ref["key"]))
            if encoded is None:
                raise KubernetesDatabaseError("referenced PostgreSQL secret key was not found")
            return base64.b64decode(encoded, validate=True).decode("utf-8")

        config_map_ref = cast(dict[str, Any] | None, value_from.get("configMapKeyRef"))
        if config_map_ref:
            config_map = self._get_resource("configmap", str(config_map_ref["name"]))
            data = cast(dict[str, str], config_map.get("data", {}))
            value = data.get(str(config_map_ref["key"]))
            if value is None:
                raise KubernetesDatabaseError("referenced PostgreSQL ConfigMap key was not found")
            return value

        raise KubernetesDatabaseError("unsupported PostgreSQL environment value source")

    def _get_resource(self, kind: str, name: str) -> dict[str, Any]:
        cache_key = (kind, name)
        cached = self._resource_cache.get(cache_key)
        if cached is not None:
            return cached

        namespace = self._required_setting(self._config.namespace)
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
        context = self._required_setting(self._config.context)
        namespace = self._required_setting(self._config.namespace)
        service = self._required_setting(self._config.service)
        local_port = self._config.local_port
        remote_port = self._config.remote_port
        command = [
            self._config.kubectl_path,
            f"--context={context}",
            "port-forward",
            "--namespace",
            namespace,
            f"service/{service}",
            f"{local_port}:{remote_port}",
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

        deadline = time.monotonic() + self._config.start_timeout_seconds
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                raise KubernetesDatabaseError(
                    f"kubectl port-forward exited with code {return_code}"
                )
            if self._port_is_open(self._config.local_port):
                return
            time.sleep(0.1)
        raise KubernetesDatabaseError("kubectl port-forward did not become ready before timeout")

    def _run_kubectl(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        command = [self._config.kubectl_path, *arguments]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._config.start_timeout_seconds,
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
    def _required_setting(value: str | None) -> str:
        if value is None:
            raise KubernetesDatabaseError("required Kubernetes setting is missing")
        return value

    @staticmethod
    def _build_configuration(
        settings: Settings,
        database_service: DatabaseService,
    ) -> _TunnelConfiguration:
        if database_service == "balance":
            return _TunnelConfiguration(
                database_service=database_service,
                kubectl_path=settings.balance_db_kubectl_path,
                context=settings.balance_db_kube_context,
                namespace=settings.balance_db_kube_namespace,
                service=settings.balance_db_kube_service,
                deployment=settings.balance_db_kube_deployment,
                container=settings.balance_db_kube_container,
                local_port=settings.balance_db_kube_local_port,
                remote_port=settings.balance_db_kube_remote_port,
                start_timeout_seconds=settings.balance_db_kube_start_timeout.total_seconds(),
            )
        return _TunnelConfiguration(
            database_service=database_service,
            kubectl_path=settings.promocodes_db_kubectl_path,
            context=settings.promocodes_db_kube_context,
            namespace=settings.promocodes_db_kube_namespace,
            service=settings.promocodes_db_kube_service,
            deployment=settings.promocodes_db_kube_deployment,
            container=settings.promocodes_db_kube_container,
            local_port=settings.promocodes_db_kube_local_port,
            remote_port=settings.promocodes_db_kube_remote_port,
            start_timeout_seconds=settings.promocodes_db_kube_start_timeout.total_seconds(),
        )
