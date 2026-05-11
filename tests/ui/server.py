"""Isolated live server fixture for UI system tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


class RecipeBookUiServer:
    """Runs the application against a temporary database and static assets."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None
        self._process: subprocess.Popen[str] | None = None
        self.port = self._free_port()

    @property
    def base_url(self) -> str:
        """Return the HTTP base URL for the running test server."""
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        """Start the application server and wait until HTTP API responds."""
        self._tempdir = tempfile.TemporaryDirectory(prefix="recipebook-ui-")
        base_dir = Path(self._tempdir.name)
        self._prepare_base_dir(base_dir)

        env = {
            **os.environ,
            "PYTHONPATH": str(self.repo_root),
            "RECIPEBOOK_UI_BASE_DIR": str(base_dir),
            "RECIPEBOOK_UI_PORT": str(self.port),
        }
        command = [
            sys.executable,
            "-c",
            (
                "import os; "
                "from pathlib import Path; "
                "from recipebook.server import run; "
                "run(Path(os.environ['RECIPEBOOK_UI_BASE_DIR']), "
                "host='127.0.0.1', port=int(os.environ['RECIPEBOOK_UI_PORT']))"
            ),
        ]
        self._process = subprocess.Popen(
            command,
            cwd=self.repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._wait_until_ready()

    def reset_data(self) -> None:
        """Reset the temporary database between tests."""
        if self._tempdir is None:
            raise RuntimeError("Test server is not started.")
        db_path = Path(self._tempdir.name) / "data" / "db.json"
        db_path.write_text(
            json.dumps({"products": [], "dishes": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def stop(self) -> None:
        """Terminate the server process and delete temporary files."""
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        if self._tempdir is not None:
            self._tempdir.cleanup()

    def _prepare_base_dir(self, base_dir: Path) -> None:
        (base_dir / "data").mkdir(parents=True, exist_ok=True)
        self.reset_data_file(base_dir)
        self._link_or_copy(self.repo_root / "static", base_dir / "static")
        self._link_or_copy(self.repo_root / "pictures", base_dir / "pictures")

    @staticmethod
    def reset_data_file(base_dir: Path) -> None:
        """Create an empty JSON database in the supplied base directory."""
        (base_dir / "data" / "db.json").write_text(
            json.dumps({"products": [], "dishes": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _link_or_copy(source: Path, destination: Path) -> None:
        try:
            destination.symlink_to(source, target_is_directory=True)
        except OSError:
            shutil.copytree(source, destination)

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + 10
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self._process and self._process.poll() is not None:
                stdout, stderr = self._process.communicate(timeout=1)
                raise RuntimeError(
                    "Recipe Book UI test server exited early.\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )
            try:
                with urlopen(f"{self.base_url}/api/meta", timeout=0.5) as response:
                    if response.status == 200:
                        return
            except Exception as exc:
                last_error = exc
                time.sleep(0.1)
        raise RuntimeError(f"Recipe Book UI test server did not start: {last_error}")

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
