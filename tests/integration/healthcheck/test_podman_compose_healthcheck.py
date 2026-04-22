import json
import os
import time
import unittest
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from tests.integration.test_utils import EnsureHealthcheckRun
from tests.integration.test_utils import ExecutionTime
from tests.integration.test_utils import RunSubprocessMixin
from tests.integration.test_utils import podman_compose_path
from tests.integration.test_utils import test_path


def compose_yaml_path() -> str:
    return os.path.join(test_path(), "healthcheck", "docker-compose.yml")


class TestComposeHealthcheck(unittest.TestCase, RunSubprocessMixin):
    def _is_running(self, container_name: str) -> bool:
        output, _ = self.run_subprocess_assert_returncode([
            "podman",
            "inspect",
            container_name,
        ])
        inspect = json.load(BytesIO(output))

        self.assertEqual(len(inspect), 1)
        self.assertIn("State", inspect[0])
        self.assertIn("Running", inspect[0]["State"])
        return inspect[0]["State"]["Running"]

    def _get_health_status(self, container_name: str) -> str:
        output, _ = self.run_subprocess_assert_returncode([
            "podman",
            "inspect",
            container_name,
        ])
        inspect = json.load(BytesIO(output))

        self.assertEqual(len(inspect), 1)
        self.assertIn("State", inspect[0])
        self.assertIn("Health", inspect[0]["State"])
        self.assertIn("Status", inspect[0]["State"]["Health"])

        return inspect[0]["State"]["Health"]["Status"]

    def _create_file_for_health_test(self, file_path: str) -> Path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return path

    def _assert_status(self, expected: str, container_name: str = "healthcheck_app_1") -> str:
        status = "unknown"
        # Total test time is ~10s: grace period (~6s) + healthcheck duration (~4s)
        # Healthcheck timing: interval 1s + timeout 1s per attempt, with 2 retries
        for _ in range(20):
            status = self._get_health_status(container_name)
            if status == expected:
                return status
            time.sleep(0.5)
        return status

    # test if healthcheck is able to change health status: starting -> healthy -> unhealthy
    def test_healthcheck(self) -> None:
        try:
            with EnsureHealthcheckRun(
                runner=self, test_case=self, container_name="healthcheck_app_1"
            ):
                # the execution time of this command must be not more than 10 seconds
                # otherwise this test case makes no sense
                with ExecutionTime(max_execution_time=timedelta(seconds=10)):
                    self.run_subprocess_assert_returncode([
                        podman_compose_path(),
                        "-f",
                        compose_yaml_path(),
                        "up",
                        "-d",
                    ])

                output, _ = self.run_subprocess_assert_returncode([
                    podman_compose_path(),
                    "-f",
                    compose_yaml_path(),
                    "ps",
                ])
                self.assertIn(b"healthcheck_app_1", output)
                self.assertTrue(self._is_running("healthcheck_app_1"))

                health = self._get_health_status("healthcheck_app_1")
                self.assertEqual(health, "starting")

                # condition for a container to become 'healthy'
                file_path = os.path.join(test_path(), "healthcheck", "health-trigger", "healthy")
                path = self._create_file_for_health_test(file_path)

                health_status = self._assert_status("healthy")
                self.assertEqual(health_status, "healthy")

                # condition for a container to become 'unhealthy'
                path.unlink()
                health_status = self._assert_status("unhealthy")
                self.assertEqual(health_status, "unhealthy")
        finally:
            self.run_subprocess_assert_returncode([
                podman_compose_path(),
                "-f",
                compose_yaml_path(),
                "down",
                "-t",
                "0",
            ])
