"""ClamAV scanning over clamd's TCP INSTREAM command (clamd documentation:
"zINSTREAM", chunks prefixed with a 4-byte big-endian length, ended by a
zero-length chunk)."""

import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str | None = None


class VirusScanner(Protocol):
    def scan_file(self, path: Path) -> ScanResult: ...


class ScanError(Exception):
    pass


class ClamdScanner:
    def __init__(self, host: str, port: int = 3310, timeout: float = 120.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def scan_file(self, path: Path) -> ScanResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as conn:
                conn.sendall(b"zINSTREAM\0")
                with path.open("rb") as handle:
                    while chunk := handle.read(CHUNK):
                        conn.sendall(struct.pack("!L", len(chunk)) + chunk)
                conn.sendall(struct.pack("!L", 0))
                reply = b""
                while not reply.endswith(b"\0"):
                    data = conn.recv(4096)
                    if not data:
                        break
                    reply += data
        except OSError as exc:
            raise ScanError(f"clamd unavailable: {exc}") from exc
        text = reply.rstrip(b"\0").decode(errors="replace")
        # "stream: OK" or "stream: Eicar-Signature FOUND" or "... ERROR"
        if text.endswith("OK"):
            return ScanResult(clean=True)
        if text.endswith("FOUND"):
            return ScanResult(
                clean=False, signature=text.removeprefix("stream: ").removesuffix(" FOUND")
            )
        raise ScanError(f"clamd error: {text[:200]}")
