"""
Default warehouse layout — plain data, not hard-coded into engine logic.

This mirrors buildDefaultWarehouseLayout() in simulator.html exactly, so a
teammate's path planner can be developed and unit-tested against this
Python object and then plugged straight into the browser demo, or vice
versa. Swap this function (or load a different JSON file) to change the
warehouse without touching engine.py.
"""

RACK_ROWS_Z = [-9, -3, 3, 9]
RACK_DEPTH = 1.6
RACK_HEIGHT = 2.3
CROSS_AISLES = [
    {"x": -6, "width": 3.0, "narrow": False},
    {"x": 9, "width": 1.8, "narrow": True},
]
X_MIN, X_MAX = -20, 20


def _segments_for_row():
    segs = []
    cursor = X_MIN
    for aisle in sorted(CROSS_AISLES, key=lambda a: a["x"]):
        gap_start = aisle["x"] - aisle["width"] / 2
        gap_end = aisle["x"] + aisle["width"] / 2
        segs.append((cursor, gap_start))
        cursor = gap_end
    segs.append((cursor, X_MAX))
    return segs


def build_default_warehouse_layout() -> dict:
    racks = []
    for row_idx, z in enumerate(RACK_ROWS_Z):
        for seg_idx, (x0, x1) in enumerate(_segments_for_row()):
            w = x1 - x0
            if w < 1:
                continue
            racks.append({
                "id": f"RACK-{row_idx}-{seg_idx}",
                "x": (x0 + x1) / 2, "z": z, "w": w, "d": RACK_DEPTH, "h": RACK_HEIGHT,
            })

    return {
        "name": "SIH26 Default Warehouse - Layout A",
        "bounds": {"xMin": -22, "xMax": 22, "zMin": -14, "zMax": 14},
        "gridScale": 1,
        "racks": racks,
        "aisles": {"crossAisles": CROSS_AISLES, "rowsZ": RACK_ROWS_Z},
        "intersections": [
            {"id": "INT-A", "x": -6, "z": -6}, {"id": "INT-B", "x": -6, "z": 0}, {"id": "INT-C", "x": -6, "z": 6},
            {"id": "INT-D", "x": 9, "z": -6, "narrow": True}, {"id": "INT-E", "x": 9, "z": 0, "narrow": True},
            {"id": "INT-F", "x": 9, "z": 6, "narrow": True},
        ],
        "pickupStations": [
            {"id": "P-01", "x": -20.5, "z": -9}, {"id": "P-02", "x": -20.5, "z": -3},
            {"id": "P-03", "x": -20.5, "z": 3}, {"id": "P-04", "x": -20.5, "z": 9},
        ],
        "dropStations": [
            {"id": "D-01", "x": 20.5, "z": -9}, {"id": "D-02", "x": 20.5, "z": -3},
            {"id": "D-03", "x": 20.5, "z": 3}, {"id": "D-04", "x": 20.5, "z": 9},
        ],
        "chargingStations": [
            {"id": "C-01", "x": -6, "z": 12.5}, {"id": "C-02", "x": 9, "z": 12.5}, {"id": "C-03", "x": -6, "z": -12.5},
        ],
        "staticObstacles": [
            {"id": "OBS-STATIC-1", "x": 0, "z": 6, "r": 0.6},
        ],
    }
