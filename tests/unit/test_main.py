# SPDX-License-Identifier: GPL-2.0

import contextlib
import io
import unittest
from unittest import mock

from podman_compose import PodmanComposeError
from podman_compose import main


class TestMain(unittest.TestCase):
    @mock.patch("podman_compose.asyncio.run")
    def test_main_shows_clean_error_for_podman_compose_error(self, mocked_run: mock.Mock) -> None:
        def fake_asyncio_run(coro: object) -> None:
            if hasattr(coro, "close"):
                coro.close()  # prevent un-awaited coroutine warnings in this unit test
            raise PodmanComposeError("External network [missing-net] does not exist")

        mocked_run.side_effect = fake_asyncio_run
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as ex:
            main()

        self.assertEqual(ex.exception.code, 1)
        self.assertEqual(
            stderr.getvalue().strip(),
            "Error: External network [missing-net] does not exist",
        )
