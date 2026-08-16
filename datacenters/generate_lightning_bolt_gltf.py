#!/usr/bin/env python3
"""Generate a stylized lightning-bolt mesh and export it as glTF.

The mesh is authored directly from vertex/index arrays rather than through a
scene or mesh library. The output is a single `.gltf` file with an embedded
base64 buffer containing positions, normals, UVs, and triangle indices.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float


def polygon_area(points: list[Vec2]) -> float:
    area = 0.0
    for index, current in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        area += current.x * nxt.y - nxt.x * current.y
    return area * 0.5


def signed_cross(a: Vec2, b: Vec2, c: Vec2) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def point_in_triangle(point: Vec2, a: Vec2, b: Vec2, c: Vec2) -> bool:
    area1 = signed_cross(point, a, b)
    area2 = signed_cross(point, b, c)
    area3 = signed_cross(point, c, a)
    has_negative = area1 < 0 or area2 < 0 or area3 < 0
    has_positive = area1 > 0 or area2 > 0 or area3 > 0
    return not (has_negative and has_positive)


def triangulate_polygon(points: list[Vec2]) -> list[tuple[int, int, int]]:
    if len(points) < 3:
        raise ValueError("Need at least three points to triangulate a polygon")

    orientation = 1.0 if polygon_area(points) > 0 else -1.0
    remaining = list(range(len(points)))
    triangles: list[tuple[int, int, int]] = []

    while len(remaining) > 3:
        ear_found = False
        for offset, curr in enumerate(remaining):
            prev = remaining[offset - 1]
            nxt = remaining[(offset + 1) % len(remaining)]
            a = points[prev]
            b = points[curr]
            c = points[nxt]
            if signed_cross(a, b, c) * orientation <= 0:
                continue
            if any(
                point_in_triangle(points[candidate], a, b, c)
                for candidate in remaining
                if candidate not in (prev, curr, nxt)
            ):
                continue
            triangles.append((prev, curr, nxt))
            del remaining[offset]
            ear_found = True
            break
        if not ear_found:
            raise ValueError("Failed to triangulate lightning-bolt silhouette")

    triangles.append((remaining[0], remaining[1], remaining[2]))
    return triangles


def normalize(vector: Vec3) -> Vec3:
    magnitude = math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)
    if magnitude == 0:
        return Vec3(0.0, 0.0, 0.0)
    return Vec3(vector.x / magnitude, vector.y / magnitude, vector.z / magnitude)


def build_lightning_outline(width: float, height: float) -> list[Vec2]:
    return [
        Vec2(-0.20 * width, 0.50 * height),
        Vec2(0.14 * width, 0.50 * height),
        Vec2(0.03 * width, 0.14 * height),
        Vec2(0.30 * width, 0.14 * height),
        Vec2(-0.07 * width, -0.50 * height),
        Vec2(0.02 * width, -0.12 * height),
        Vec2(-0.24 * width, -0.12 * height),
    ]


def build_mesh(width: float, height: float, thickness: float) -> tuple[
    list[float],
    list[float],
    list[float],
    list[int],
    dict[str, list[float]],
]:
    outline = build_lightning_outline(width, height)
    # Keep the silhouette counterclockwise so face winding and side outward
    # normals stay consistent throughout extrusion.
    if polygon_area(outline) < 0:
        outline = list(reversed(outline))
    front_z = thickness * 0.5
    back_z = -front_z
    face_triangles = triangulate_polygon(outline)

    min_x = min(point.x for point in outline)
    max_x = max(point.x for point in outline)
    min_y = min(point.y for point in outline)
    max_y = max(point.y for point in outline)
    span_x = max_x - min_x
    span_y = max_y - min_y

    positions: list[float] = []
    normals: list[float] = []
    uvs: list[float] = []
    indices: list[int] = []

    def add_vertex(position: Vec3, normal: Vec3, uv: tuple[float, float]) -> int:
        index = len(positions) // 3
        positions.extend((position.x, position.y, position.z))
        normals.extend((normal.x, normal.y, normal.z))
        uvs.extend(uv)
        return index

    front_indices: list[int] = []
    back_indices: list[int] = []
    for point in outline:
        uv = ((point.x - min_x) / span_x, (point.y - min_y) / span_y)
        front_indices.append(add_vertex(Vec3(point.x, point.y, front_z), Vec3(0.0, 0.0, 1.0), uv))
        back_indices.append(add_vertex(Vec3(point.x, point.y, back_z), Vec3(0.0, 0.0, -1.0), uv))

    for a, b, c in face_triangles:
        indices.extend((front_indices[a], front_indices[b], front_indices[c]))
        indices.extend((back_indices[c], back_indices[b], back_indices[a]))

    perimeter = 0.0
    edge_lengths: list[float] = []
    for index, current in enumerate(outline):
        nxt = outline[(index + 1) % len(outline)]
        length = math.hypot(nxt.x - current.x, nxt.y - current.y)
        edge_lengths.append(length)
        perimeter += length

    perimeter_cursor = 0.0
    for index, current in enumerate(outline):
        nxt = outline[(index + 1) % len(outline)]
        edge = Vec3(nxt.x - current.x, nxt.y - current.y, 0.0)
        outward = normalize(Vec3(edge.y, -edge.x, 0.0))
        u0 = perimeter_cursor / perimeter
        u1 = (perimeter_cursor + edge_lengths[index]) / perimeter
        v0 = 0.0
        v1 = 1.0
        side_vertices = [
            add_vertex(Vec3(current.x, current.y, front_z), outward, (u0, v1)),
            add_vertex(Vec3(nxt.x, nxt.y, front_z), outward, (u1, v1)),
            add_vertex(Vec3(nxt.x, nxt.y, back_z), outward, (u1, v0)),
            add_vertex(Vec3(current.x, current.y, back_z), outward, (u0, v0)),
        ]
        indices.extend(
            (
                side_vertices[0],
                side_vertices[2],
                side_vertices[1],
                side_vertices[0],
                side_vertices[3],
                side_vertices[2],
            )
        )
        perimeter_cursor += edge_lengths[index]

    placements = {
        "root": [0.0, 0.0, 0.0],
        "pivot_top": [0.0, max_y * 0.48, 0.0],
        "pivot_mid": [0.0, 0.0, 0.0],
        "pivot_tip": [width * 0.22, min_y * 0.92, 0.0],
        "impact_core": [-width * 0.08, -height * 0.03, 0.0],
        "front_emitter": [0.0, 0.0, front_z],
        "back_emitter": [0.0, 0.0, back_z],
    }

    return positions, normals, uvs, indices, placements


def pack_floats(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def pack_uints(values: list[int]) -> bytes:
    return struct.pack(f"<{len(values)}I", *values)


def align4(payload: bytearray) -> None:
    while len(payload) % 4:
        payload.append(0)


def build_gltf(
    positions: list[float],
    normals: list[float],
    uvs: list[float],
    indices: list[int],
    placements: dict[str, list[float]],
    outline_2d: list[Vec2],
) -> dict:
    buffer = bytearray()
    buffer_views = []
    accessors = []

    def append_blob(blob: bytes, target: int | None) -> tuple[int, int]:
        offset = len(buffer)
        buffer.extend(blob)
        align4(buffer)
        view_index = len(buffer_views)
        entry = {"buffer": 0, "byteOffset": offset, "byteLength": len(blob)}
        if target is not None:
            entry["target"] = target
        buffer_views.append(entry)
        return view_index, offset

    def append_accessor(
        blob: bytes,
        target: int | None,
        component_type: int,
        count: int,
        accessor_type: str,
        minimum: list[float] | None = None,
        maximum: list[float] | None = None,
    ) -> int:
        view_index, _ = append_blob(blob, target)
        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": count,
            "type": accessor_type,
        }
        if minimum is not None:
            accessor["min"] = minimum
        if maximum is not None:
            accessor["max"] = maximum
        accessors.append(accessor)
        return len(accessors) - 1

    xs = positions[0::3]
    ys = positions[1::3]
    zs = positions[2::3]
    pos_accessor = append_accessor(
        pack_floats(positions),
        34962,
        5126,
        len(positions) // 3,
        "VEC3",
        [min(xs), min(ys), min(zs)],
        [max(xs), max(ys), max(zs)],
    )
    normal_accessor = append_accessor(pack_floats(normals), 34962, 5126, len(normals) // 3, "VEC3")
    uv_accessor = append_accessor(pack_floats(uvs), 34962, 5126, len(uvs) // 2, "VEC2")
    index_accessor = append_accessor(
        pack_uints(indices),
        34963,
        5125,
        len(indices),
        "SCALAR",
        [min(indices)],
        [max(indices)],
    )

    encoded = base64.b64encode(bytes(buffer)).decode("ascii")
    mesh_node_index = 0
    child_nodes = list(range(1, len(placements)))

    nodes = [
        {
            "name": "LightningBolt",
            "mesh": 0,
            "children": child_nodes,
            "extras": {
                "placements": placements,
                "animationHints": {
                    "spine": ["pivot_top", "pivot_mid", "pivot_tip"],
                    "emitters": ["front_emitter", "back_emitter"],
                    "impactPoint": "impact_core",
                },
            },
        }
    ]

    placement_names = [name for name in placements if name != "root"]
    for name in placement_names:
        nodes.append({"name": name, "translation": placements[name]})

    return {
        "asset": {"version": "2.0", "generator": "generate_lightning_bolt_gltf.py"},
        "scene": 0,
        "scenes": [{"nodes": [mesh_node_index]}],
        "nodes": nodes,
        "meshes": [
            {
                "name": "LightningBoltMesh",
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": pos_accessor,
                            "NORMAL": normal_accessor,
                            "TEXCOORD_0": uv_accessor,
                        },
                        "indices": index_accessor,
                        "mode": 4,
                    }
                ],
            }
        ],
        "buffers": [
            {
                "byteLength": len(buffer),
                "uri": f"data:application/octet-stream;base64,{encoded}",
            }
        ],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        default=Path("lightning-bolt.gltf"),
        type=Path,
        help="Output glTF path",
    )
    parser.add_argument("--width", type=float, default=1.0, help="Overall bolt width")
    parser.add_argument("--height", type=float, default=1.8, help="Overall bolt height")
    parser.add_argument("--thickness", type=float, default=0.18, help="Extrusion depth")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outline = build_lightning_outline(args.width, args.height)
    positions, normals, uvs, indices, placements = build_mesh(
        width=args.width,
        height=args.height,
        thickness=args.thickness,
    )
    gltf = build_gltf(positions, normals, uvs, indices, placements, outline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(gltf, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.output} with "
        f"{len(positions) // 3} vertices and {len(indices) // 3} triangles"
    )


if __name__ == "__main__":
    main()
