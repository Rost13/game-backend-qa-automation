from __future__ import annotations

import subprocess
from collections.abc import Callable
from types import ModuleType
from typing import Protocol

import httpx
import pytest

from qa_automation.config import Settings
from qa_automation.db import clickhouse_kubernetes, kubernetes
from qa_automation.db.clickhouse_kubernetes import KubectlClickHouseTunnel
from qa_automation.db.kubernetes import KubectlPostgresTunnel, KubernetesDatabaseError
from qa_automation.db.stat_api import StatClickHouseDatabase


class _KubectlRunner(Protocol):
    def _run_kubectl(self, *arguments: str) -> subprocess.CompletedProcess[str]: ...


@pytest.mark.parametrize(
    ("module", "factory"),
    [
        (kubernetes, lambda settings: KubectlPostgresTunnel(settings)),
        (clickhouse_kubernetes, lambda settings: KubectlClickHouseTunnel(settings)),
    ],
)
def test_kubectl_failure_omits_process_output(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    factory: Callable[[Settings], _KubectlRunner],
) -> None:
    stdout_secret = "internal-resource-name"
    stderr_secret = "server-response-with-sensitive-context"

    def failed_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["kubectl"],
            returncode=1,
            stdout=stdout_secret,
            stderr=stderr_secret,
        )

    monkeypatch.setattr(module.subprocess, "run", failed_run)
    tunnel = factory(Settings(_env_file=None))

    with pytest.raises(KubernetesDatabaseError) as captured:
        tunnel._run_kubectl("get", "deployment")

    diagnostic = str(captured.value)
    assert "code 1" in diagnostic
    assert stdout_secret not in diagnostic
    assert stderr_secret not in diagnostic


def test_clickhouse_http_failure_omits_url_database_and_parameters() -> None:
    database_name = "private-database-name"
    host = "private-db.example.internal"
    settings = Settings(
        _env_file=None,
        stat_clickhouse_host=host,
        stat_clickhouse_database=database_name,
        stat_clickhouse_user="qa-user",
        stat_clickhouse_password="test-password",
    )
    database = StatClickHouseDatabase(settings)
    database._client.close()
    database._client = httpx.Client(
        base_url=f"https://{host}",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, request=request, text="access denied")
        ),
    )

    try:
        with pytest.raises(RuntimeError) as captured:
            database.database_name()
    finally:
        database.close()

    diagnostic = str(captured.value)
    assert "HTTP 401" in diagnostic
    assert host not in diagnostic
    assert database_name not in diagnostic
    assert "access denied" not in diagnostic
