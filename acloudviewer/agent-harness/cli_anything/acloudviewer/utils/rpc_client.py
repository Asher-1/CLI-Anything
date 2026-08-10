"""WebSocket JSON-RPC 2.0 client for ACloudViewer's qJSonRPCPlugin."""

from __future__ import annotations

import json
import logging
import sys
import threading
from typing import Any

_id_counter = 0
_id_lock = threading.Lock()
_log = logging.getLogger("acloudviewer.rpc")


def _next_id() -> int:
    global _id_counter
    with _id_lock:
        _id_counter += 1
        return _id_counter


class RPCError(Exception):
    def __init__(self, code: int, message: str, method: str = "",
                 data: Any = None):
        self.code = code
        self.message = message
        self.method = method
        self.data = data
        parts = [f"RPC error {code}"]
        if method:
            parts[0] += f" [{method}]"
        parts.append(message)
        if data:
            parts.append(f"data={json.dumps(data, default=str)}")
        super().__init__(": ".join(parts))


class ACloudViewerRPCClient:
    """Synchronous wrapper around a WebSocket JSON-RPC connection.

    Provides typed convenience methods for every RPC method exposed by
    qJSonRPCPlugin (33 methods).  All calls log request/response at DEBUG
    level and errors at ERROR level to aid diagnosis.
    """

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
        request_json = json.dumps(request)
        _log.debug("RPC >>> %s", request_json)
        try:
            self._ws.send(request_json)
            raw = self._ws.recv()
        except Exception as exc:
            _log.error("RPC connection error calling '%s': %s", method, exc)
            raise

        _log.debug("RPC <<< %s", raw[:2000] if len(raw) > 2000 else raw)
        response = json.loads(raw)

        if "error" in response:
            err = response["error"]
            code = err.get("code", -1)
            msg = err.get("message", "Unknown")
            data = err.get("data")
            _log.error("RPC error calling '%s' (code=%d): %s | data=%s | params=%s",
                       method, code, msg, json.dumps(data, default=str),
                       json.dumps(params or {}))
            raise RPCError(code, msg, method=method, data=data)
        return response.get("result")

    # ── Session / connectivity ──────────────────────────────────────────

    def ping(self) -> str:
        return self.call("ping")

    def list_methods(self) -> list[dict]:
        return self.call("methods.list")

    # ── File I/O ────────────────────────────────────────────────────────

    def open_file(self, filename: str, silent: bool = True,
                  transformation: list[float] | None = None) -> dict:
        params: dict[str, Any] = {"filename": filename}
        if silent:
            params["silent"] = True
        if transformation:
            params["transformation"] = transformation
        return self.call("open", params)

    def export_entity(self, entity_id: int, filename: str,
                      filter_name: str = "") -> dict:
        params: dict[str, Any] = {"entity_id": entity_id, "filename": filename}
        if filter_name:
            params["filter"] = filter_name
        return self.call("export", params)

    def file_convert(self, input_path: str, output_path: str,
                     input_filter: str = "", output_filter: str = "") -> dict:
        params: dict[str, Any] = {"input": input_path, "output": output_path}
        if input_filter:
            params["input_filter"] = input_filter
        if output_filter:
            params["output_filter"] = output_filter
        return self.call("file.convert", params)

    def clear(self) -> None:
        self.call("clear")

    # ── Scene graph ─────────────────────────────────────────────────────

    def scene_list(self, recursive: bool = True) -> list[dict]:
        return self.call("scene.list", {"recursive": recursive})

    def scene_info(self, entity_id: int) -> dict:
        return self.call("scene.info", {"entity_id": entity_id})

    def scene_remove(self, entity_id: int) -> None:
        self.call("scene.remove", {"entity_id": entity_id})

    def scene_set_visible(self, entity_id: int, visible: bool) -> None:
        self.call("scene.setVisible", {"entity_id": entity_id, "visible": visible})

    def scene_select(self, entity_ids: list[int]) -> None:
        self.call("scene.select", {"entity_ids": entity_ids})

    # ── Entity operations ───────────────────────────────────────────────

    def entity_rename(self, entity_id: int, name: str) -> None:
        self.call("entity.rename", {"entity_id": entity_id, "name": name})

    def entity_set_color(self, entity_id: int, r: int, g: int, b: int) -> int:
        return self.call("entity.setColor",
                         {"entity_id": entity_id, "r": r, "g": g, "b": b})

    # ── Cloud processing ────────────────────────────────────────────────

    def cloud_compute_normals(self, entity_id: int, radius: float = 0.0) -> dict:
        return self.call("cloud.computeNormals",
                         {"entity_id": entity_id, "radius": radius})

    def cloud_subsample(self, entity_id: int, method: str = "spatial",
                        step: float = 0.05, count: int = 10000) -> dict:
        return self.call("cloud.subsample", {
            "entity_id": entity_id, "method": method,
            "step": step, "count": count,
        })

    def cloud_crop(self, entity_id: int,
                   min_x: float = 0, min_y: float = 0, min_z: float = 0,
                   max_x: float = 1, max_y: float = 1, max_z: float = 1) -> dict:
        return self.call("cloud.crop", {
            "entity_id": entity_id,
            "min_x": min_x, "min_y": min_y, "min_z": min_z,
            "max_x": max_x, "max_y": max_y, "max_z": max_z,
        })

    def cloud_get_scalar_fields(self, entity_id: int) -> list[dict]:
        return self.call("cloud.getScalarFields", {"entity_id": entity_id})

    def cloud_paint_uniform(self, entity_id: int,
                            r: int = 255, g: int = 255, b: int = 255) -> dict:
        return self.call("cloud.paintUniform",
                         {"entity_id": entity_id, "r": r, "g": g, "b": b})

    def cloud_paint_by_height(self, entity_id: int, axis: str = "z") -> dict:
        return self.call("cloud.paintByHeight",
                         {"entity_id": entity_id, "axis": axis})

    def cloud_paint_by_scalar_field(self, entity_id: int,
                                     field_index: int = 0) -> dict:
        return self.call("cloud.paintByScalarField",
                         {"entity_id": entity_id, "field_index": field_index})

    # ── Mesh processing ─────────────────────────────────────────────────

    def mesh_simplify(self, entity_id: int, method: str = "quadric",
                      target_triangles: int = 10000,
                      voxel_size: float = 0.05) -> dict:
        return self.call("mesh.simplify", {
            "entity_id": entity_id, "method": method,
            "target_triangles": target_triangles, "voxel_size": voxel_size,
        })

    def mesh_smooth(self, entity_id: int, method: str = "laplacian",
                    iterations: int = 5, lambda_val: float = 0.5,
                    mu: float = -0.53) -> dict:
        params: dict[str, Any] = {
            "entity_id": entity_id, "method": method,
            "iterations": iterations, "lambda": lambda_val,
        }
        if method == "taubin":
            params["mu"] = mu
        return self.call("mesh.smooth", params)

    def mesh_subdivide(self, entity_id: int, method: str = "midpoint",
                       iterations: int = 1) -> dict:
        return self.call("mesh.subdivide", {
            "entity_id": entity_id, "method": method, "iterations": iterations,
        })

    def mesh_sample_points(self, entity_id: int, method: str = "uniform",
                           count: int = 100000) -> dict:
        return self.call("mesh.samplePoints", {
            "entity_id": entity_id, "method": method, "count": count,
        })

    # ── View control ────────────────────────────────────────────────────

    def set_view(self, orientation: str) -> int:
        return self.call("view.setOrientation", {"orientation": orientation})

    def zoom_fit(self, entity_id: int | None = None) -> int:
        params: dict[str, Any] = {}
        if entity_id is not None:
            params["entity_id"] = entity_id
        return self.call("view.zoomFit", params)

    def view_refresh(self) -> int:
        return self.call("view.refresh")

    def view_set_perspective(self, mode: str = "object") -> int:
        return self.call("view.setPerspective", {"mode": mode})

    def view_set_point_size(self, action: str = "increase") -> int:
        return self.call("view.setPointSize", {"action": action})

    def view_screenshot(self, filename: str) -> dict:
        return self.call("view.screenshot", {"filename": filename})

    def view_get_camera(self) -> dict:
        return self.call("view.getCamera")

    # ── Transform ───────────────────────────────────────────────────────

    def transform_apply(self, entity_id: int, matrix: list[float]) -> int:
        return self.call("transform.apply",
                         {"entity_id": entity_id, "matrix": matrix})

    # ── Cloud scalar-field management ──────────────────────────────────

    def cloud_set_active_sf(self, entity_id: int, field_index: int = -1,
                            field_name: str = "") -> dict:
        params: dict[str, Any] = {"entity_id": entity_id}
        if field_name:
            params["field_name"] = field_name
        else:
            params["field_index"] = field_index
        return self.call("cloud.setActiveSf", params)

    def cloud_remove_sf(self, entity_id: int, field_index: int = -1,
                        field_name: str = "") -> dict:
        params: dict[str, Any] = {"entity_id": entity_id}
        if field_name:
            params["field_name"] = field_name
        else:
            params["field_index"] = field_index
        return self.call("cloud.removeSf", params)

    def cloud_remove_all_sfs(self, entity_id: int) -> dict:
        return self.call("cloud.removeAllSfs", {"entity_id": entity_id})

    def cloud_rename_sf(self, entity_id: int, new_name: str,
                        field_index: int = -1, old_name: str = "") -> dict:
        params: dict[str, Any] = {"entity_id": entity_id, "new_name": new_name}
        if old_name:
            params["old_name"] = old_name
        else:
            params["field_index"] = field_index
        return self.call("cloud.renameSf", params)

    def cloud_filter_sf(self, entity_id: int, min_val: float = 0,
                        max_val: float = 1, field_index: int = -1,
                        field_name: str = "") -> dict:
        params: dict[str, Any] = {
            "entity_id": entity_id, "min": min_val, "max": max_val,
        }
        if field_name:
            params["field_name"] = field_name
        elif field_index >= 0:
            params["field_index"] = field_index
        return self.call("cloud.filterSf", params)

    def cloud_coord_to_sf(self, entity_id: int, dimension: str = "z") -> dict:
        return self.call("cloud.coordToSF",
                         {"entity_id": entity_id, "dimension": dimension})

    # ── Cloud geometry ──────────────────────────────────────────────────

    def cloud_remove_rgb(self, entity_id: int) -> dict:
        return self.call("cloud.removeRgb", {"entity_id": entity_id})

    def cloud_remove_normals(self, entity_id: int) -> dict:
        return self.call("cloud.removeNormals", {"entity_id": entity_id})

    def cloud_invert_normals(self, entity_id: int) -> dict:
        return self.call("cloud.invertNormals", {"entity_id": entity_id})

    def cloud_merge(self, entity_ids: list[int]) -> dict:
        return self.call("cloud.merge", {"entity_ids": entity_ids})

    # ── Cloud analysis (GUI RPC) ─────────────────────────────────────

    def cloud_density(self, entity_id: int, radius: float = 0.05) -> dict:
        return self.call("cloud.density",
                         {"entity_id": entity_id, "radius": radius})

    def cloud_curvature(self, entity_id: int, curvature_type: str = "MEAN",
                        radius: float = 0.05) -> dict:
        return self.call("cloud.curvature",
                         {"entity_id": entity_id, "type": curvature_type,
                          "radius": radius})

    def cloud_roughness(self, entity_id: int, radius: float = 0.1) -> dict:
        return self.call("cloud.roughness",
                         {"entity_id": entity_id, "radius": radius})

    def cloud_geometric_feature(self, entity_id: int,
                                feature_type: str = "SURFACE_VARIATION",
                                kernel_size: float = 0.1) -> dict:
        return self.call("cloud.geometricFeature",
                         {"entity_id": entity_id, "type": feature_type,
                          "kernel_size": kernel_size})

    def cloud_approx_density(self, entity_id: int,
                             density_type: str = "PRECISE") -> dict:
        return self.call("cloud.approxDensity",
                         {"entity_id": entity_id, "density_type": density_type})

    def cloud_color_banding(self, entity_id: int, axis: str = "Z",
                            frequency: float = 10.0) -> dict:
        return self.call("cloud.colorBanding",
                         {"entity_id": entity_id, "axis": axis,
                          "frequency": frequency})

    def cloud_sor_filter(self, entity_id: int, knn: int = 6,
                         sigma: float = 1.0) -> dict:
        return self.call("cloud.sorFilter",
                         {"entity_id": entity_id, "knn": knn, "sigma": sigma})

    def cloud_sf_arithmetic(self, entity_id: int, sf_index: int = 0,
                            operation: str = "SQRT") -> dict:
        return self.call("cloud.sfArithmetic",
                         {"entity_id": entity_id, "sf_index": sf_index,
                          "operation": operation})

    def cloud_sf_operation(self, entity_id: int, sf_index: int = 0,
                           operation: str = "ADD", value: float = 0.0) -> dict:
        return self.call("cloud.sfOperation",
                         {"entity_id": entity_id, "sf_index": sf_index,
                          "operation": operation, "value": value})

    def cloud_sf_gradient(self, entity_id: int) -> dict:
        return self.call("cloud.sfGradient", {"entity_id": entity_id})

    def cloud_sf_convert_to_rgb(self, entity_id: int) -> dict:
        return self.call("cloud.sfConvertToRGB", {"entity_id": entity_id})

    def cloud_octree_normals(self, entity_id: int,
                             radius: str = "AUTO") -> dict:
        return self.call("cloud.octreeNormals",
                         {"entity_id": entity_id, "radius": radius})

    def cloud_orient_normals_mst(self, entity_id: int, knn: int = 6) -> dict:
        return self.call("cloud.orientNormalsMST",
                         {"entity_id": entity_id, "knn": knn})

    def cloud_clear_normals(self, entity_id: int) -> dict:
        return self.call("cloud.clearNormals", {"entity_id": entity_id})

    def cloud_normals_to_sfs(self, entity_id: int) -> dict:
        return self.call("cloud.normalsToSFs", {"entity_id": entity_id})

    def cloud_normals_to_dip(self, entity_id: int) -> dict:
        return self.call("cloud.normalsToDip", {"entity_id": entity_id})

    def cloud_extract_cc(self, entity_id: int, min_points: int = 10,
                         octree_level: int = 6) -> dict:
        return self.call("cloud.extractConnectedComponents",
                         {"entity_id": entity_id, "min_points": min_points,
                          "octree_level": octree_level})

    def cloud_best_fit_plane(self, entity_id: int,
                             make_horiz: bool = False) -> dict:
        return self.call("cloud.bestFitPlane",
                         {"entity_id": entity_id, "make_horiz": make_horiz})

    def cloud_delaunay(self, entity_id: int) -> dict:
        return self.call("cloud.delaunay", {"entity_id": entity_id})

    # ── Mesh extended ──────────────────────────────────────────────────

    def mesh_extract_vertices(self, entity_id: int) -> dict:
        return self.call("mesh.extractVertices", {"entity_id": entity_id})

    def mesh_flip_triangles(self, entity_id: int) -> dict:
        return self.call("mesh.flipTriangles", {"entity_id": entity_id})

    def mesh_volume(self, entity_id: int) -> dict:
        return self.call("mesh.volume", {"entity_id": entity_id})

    def mesh_merge(self, entity_ids: list[int]) -> dict:
        return self.call("mesh.merge", {"entity_ids": entity_ids})

    # ── Reconstruction (GUI) ────────────────────────────────────────────

    def colmap_reconstruct(self, image_path: str, workspace_path: str,
                           **kwargs) -> dict:
        params: dict[str, Any] = {
            "image_path": image_path, "workspace_path": workspace_path,
        }
        params.update(kwargs)
        return self.call("colmap.reconstruct", params)

    def colmap_run(self, command: str, args: list[str] | None = None,
                   kwargs_: dict[str, str] | None = None,
                   colmap_binary: str = "colmap",
                   timeout_ms: int = 3600000) -> dict:
        params: dict[str, Any] = {
            "command": command,
            "colmap_binary": colmap_binary,
            "timeout_ms": timeout_ms,
        }
        if args:
            params["args"] = args
        if kwargs_:
            params["kwargs"] = kwargs_
        return self.call("colmap.run", params)

    # ── Context manager ─────────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
