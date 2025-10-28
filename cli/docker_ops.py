"""Wrapper around docker compose commands."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .exceptions import DockerError


class DockerRunner:
    """Thin wrapper that shells out to docker compose."""

    def __init__(self, compose_bin: str) -> None:
        self._compose_bin = shlex.split(compose_bin)

    def compose(
        self,
        compose_file: Path,
        args: Sequence[str],
        *,
        check: bool = True,
        capture_output: bool = False,
        text: bool = True,
        input_data: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        cmd = [*self._compose_bin, "-f", str(compose_file), *args]
        try:
            return subprocess.run(  # noqa: S603
                cmd,
                check=check,
                capture_output=capture_output,
                text=text,
                input=input_data,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - plumbing
            raise DockerError(f"Command failed: {' '.join(cmd)}\n{exc.stderr}") from exc

    def up(self, compose_file: Path, *, detach: bool = True) -> None:
        args: List[str] = ["up"]
        if detach:
            args.append("-d")
        self.compose(compose_file, args)

    def down(self, compose_file: Path, *, volumes: bool = True) -> None:
        args: List[str] = ["down"]
        if volumes:
            args.append("--volumes")
        self.compose(compose_file, args, check=False)

    def exec(
        self,
        compose_file: Path,
        service: str,
        command: Sequence[str],
        *,
        env: Optional[Iterable[tuple[str, str]]] = None,
        input_data: Optional[str] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        args = ["exec", "-T"]
        if env:
            for key, value in env:
                args.extend(["-e", f"{key}={value}"])
        args.extend([service, *command])
        return self.compose(
            compose_file,
            args,
            check=check,
            capture_output=True,
            text=True,
            input_data=input_data,
        )

    def logs(self, compose_file: Path, service: Optional[str] = None, *, tail: int = 100) -> str:
        args = ["logs", "--tail", str(tail)]
        if service:
            args.append(service)
        result = self.compose(
            compose_file,
            args,
            capture_output=True,
        )
        return result.stdout
