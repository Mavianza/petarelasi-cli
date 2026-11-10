from collections import Counter
from dataclasses import dataclass
from math import ceil, sqrt

from .schema import Schema, Table


HEADER = 40
ROW = 28
WIDTH = 278
MARGIN = 24
LANE = 13
GAP = 38
PALETTE = ("#1766a4", "#71509a", "#0f776d", "#a74453", "#9a5915")
Point = tuple[int, int]


@dataclass(frozen=True)
class Box:
    table: Table
    key: str
    x: int
    y: int

    @property
    def height(self) -> int:
        return HEADER + ROW * len(self.table.columns)

    def row_y(self, index: int) -> int:
        return self.y + HEADER + ROW * index

    def port(self, index: int, side: int, *, target: bool) -> Point:
        return self.x + side * WIDTH, self.row_y(index) + (18 if target else 10)


@dataclass(frozen=True)
class Wire:
    key: str
    source: Box
    target: Box
    source_row: int
    target_row: int
    source_side: int
    target_side: int
    color: str
    points: tuple[Point, ...]


@dataclass(frozen=True)
class Diagram:
    boxes: tuple[Box, ...]
    wires: tuple[Wire, ...]
    width: int
    height: int


def layout(schema: Schema) -> Diagram:
    columns = min(4, ceil(sqrt(len(schema.tables))))
    grid = {t.name: divmod(i, columns) for i, t in enumerate(schema.tables)}
    indices = {t.name: {c.name: j for j, c in enumerate(t.columns)} for t in schema.tables}
    vertical = Counter()
    horizontal = Counter()
    endpoints = []
    for number, ref in enumerate(schema.foreign_keys, 1):
        row, col = grid[ref.table]
        _, target_col = grid[ref.references]
        if col == target_col:
            source_side = target_side = 1
        else:
            source_side = int(col < target_col)
            target_side = 1 - source_side
        source_gap = col + source_side
        target_gap = target_col + target_side
        for pair, (left, right) in enumerate(zip(ref.columns, ref.ref_columns), 1):
            key = f"F{number}.{pair}" if len(ref.columns) > 1 else f"F{number}"
            endpoints.append((key, ref.table, ref.references, left, right, source_side, target_side,
                              (source_gap, vertical[source_gap]), (target_gap, vertical[target_gap] + (source_gap == target_gap)),
                              (row, horizontal[row]), PALETTE[(number - 1) % len(PALETTE)]))
            vertical[source_gap] += 1
            vertical[target_gap] += 1
            horizontal[row] += 1

    table_x = []
    gap_x = []
    x = MARGIN
    for col in range(columns + 1):
        gap_x.append(x)
        x += GAP + LANE * vertical[col]
        if col < columns:
            table_x.append(x)
            x += WIDTH

    table_y = []
    gap_y = []
    y = MARGIN
    for offset in range(0, len(schema.tables), columns):
        row = offset // columns
        shelf = schema.tables[offset:offset + columns]
        table_y.append(y)
        y += max(HEADER + ROW * len(table.columns) for table in shelf)
        gap_y.append(y)
        y += GAP + LANE * horizontal[row]

    boxes = {}
    for i, table in enumerate(schema.tables):
        row, col = grid[table.name]
        boxes[table.name] = Box(table, f"table-{i}", table_x[col], table_y[row])

    wires = []
    for key, source, target, left, right, s_side, t_side, s_track, t_track, h_track, color in endpoints:
        s_box, t_box = boxes[source], boxes[target]
        s_row, t_row = indices[source][left], indices[target][right]
        start = s_box.port(s_row, s_side, target=False)
        end = t_box.port(t_row, t_side, target=True)
        sx = gap_x[s_track[0]] + GAP // 2 + LANE * s_track[1]
        tx = gap_x[t_track[0]] + GAP // 2 + LANE * t_track[1]
        turn = gap_y[h_track[0]] + GAP // 2 + LANE * h_track[1]
        points = (start, (sx, start[1]), (sx, turn), (tx, turn), (tx, end[1]), end)
        wires.append(Wire(key, s_box, t_box, s_row, t_row, s_side, t_side, color, points))
    return Diagram(tuple(boxes.values()), tuple(wires), x + MARGIN, y + MARGIN)
