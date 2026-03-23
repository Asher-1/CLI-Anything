"""WebSocket JSON-RPC 2.0 client for ACloudViewer's qJSonRPCPlugin."""

from __future__ import annotations

import json
import threading
from typing import Any

_id_counter = 0
_id_lock = threading.Lock()


def _next_id() -> int:
    global _id_counter
    with _id_lock:
        _id_counter += 1
        return _id_counter


class RPCError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"RPC error {code}: {message}")


class ACloudViewerRPCClient:
    """Synchronous wrapper around a WebSocket JSON-RPC connection."""

    def __init__(self, url: str = "ws://localhost:6001"):
        self._url = url
        self._ws = None

    def connect(self) -> None:
        import websockets.sync.client as ws_sync
        self._ws = ws_sync.connect(self._url)

    def close(self) -> None:
        if self._ws:
            self._ws.close()
            self._ws = None

    def is_connected(self) -> bool:
        return self._ws is not None

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self._ws:
            self.connect()

        request = {
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": method,
            "params": params or {},
        }
        self._ws.send(json.dumps(request))
        raw = self._ws.recv()
        response = json.loads(raw)

        if "error" in response:
            err = response["error"]
            raise RPCError(err.get("code", -1), err.get("message", "Unknown"))
        return response.get("result")

    # -- convenience wrappers ------------------------------------------------

    def ping(self) -> str:
        return self.call("ping")

    def open_file(self, filename: str, silent: bool = True) -> dict:
        params: dict[str, Any] = {"filename": filename}
        if silent:
            params["silent"] = True
        return self.call("open", params)

    def clear(self) -> None:
        self.call("clear")

    def scene_list(self, recursive: bool = True) -> list[dict]:
        return self.call("scene.list", {"recursive": recursive})

    def scene_info(self, entity_id: int) -> dict:
        return self.call("scene.info", {"entity_id": entity_id})

    def export_entity(self, entity_id: int, filename: str) -> dict:
        return self.call("export", {"entity_id": entity_id, "filename": filename})

    def set_view(self, orientation: str) -> None:
        self.call("view.setOrientation", {"orientation": orientation})

    def zoom_fit(self) -> None:
        self.call("view.zoomFit")

    def list_methods(self) -> list[dict]:
        return self.call("methods.list")

    def file_convert(self, input_path: str, output_path: str) -> dict:
        return self.call("file.convert", {"input": input_path, "output": output_path})

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
