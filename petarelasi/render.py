import xml.etree.ElementTree as ET

from .layout import Diagram, HEADER, ROW, WIDTH


def child(container, tag, **attributes):
    return ET.SubElement(container, tag, {k: str(v) for k, v in attributes.items()})


def xml_bytes(root) -> bytes:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def row_labels(diagram):
    foreign = {(wire.source.key, wire.source_row) for wire in diagram.wires}
    for box in diagram.boxes:
        labels = []
        for i, column in enumerate(box.table.columns):
            badges = []
            if column.pk:
                badges.append("PK" + str(column.pk))
            if (box.key, i) in foreign:
                badges.append("FK")
            prefix = ("[" + "/".join(badges) + "] ") if badges else ""
            labels.append(prefix + column.name + ("  ·  " + column.type if column.type else ""))
        yield box, labels


def drawio(diagram: Diagram) -> bytes:
    file = ET.Element("mxfile")
    page = child(file, "diagram", id="erd", name="ERD")
    model = child(page, "mxGraphModel", dx="0", dy="0", grid="0", page="0",
                  pageWidth=diagram.width, pageHeight=diagram.height)
    cells = child(model, "root")
    child(cells, "mxCell", id=0)
    child(cells, "mxCell", id=1, parent=0)
    for box, labels in row_labels(diagram):
        table = child(cells, "mxCell", id=box.key, value=box.table.name, parent=1, vertex=1,
                      style="swimlane;horizontal=1;startSize=40;collapsible=0;html=0;"
                            "whiteSpace=wrap;fillColor=#20364f;swimlaneFillColor=#ffffff;"
                            "fontColor=#ffffff;strokeColor=#90a5ba;fontStyle=1;")
        child(table, "mxGeometry", x=box.x, y=box.y, width=WIDTH, height=box.height, **{"as": "geometry"})
        for index, label in enumerate(labels):
            shade = "#f1f5f9" if index % 2 == 0 else "#ffffff"
            column = child(cells, "mxCell", id=f"{box.key}-c{index}", value=label, parent=box.key, vertex=1,
                           style="shape=rectangle;align=left;verticalAlign=middle;html=0;"
                                 f"whiteSpace=wrap;overflow=hidden;spacingLeft=8;strokeColor=none;fillColor={shade};")
            child(column, "mxGeometry", x=0, y=HEADER + ROW * index, width=WIDTH, height=ROW,
                  **{"as": "geometry"})
    for wire in diagram.wires:
        edge = child(cells, "mxCell", id="edge-" + wire.key, value=wire.key, parent=1, edge=1,
                     source=f"{wire.source.key}-c{wire.source_row}",
                     target=f"{wire.target.key}-c{wire.target_row}",
                     style=f"noEdgeStyle=1;orthogonal=1;html=0;strokeColor={wire.color};"
                           "endArrow=block;endFill=1;strokeWidth=1.5;labelBackgroundColor=#ffffff;"
                           f"exitX={wire.source_side};exitY={10 / ROW:.8f};exitPerimeter=0;"
                           f"entryX={wire.target_side};entryY={18 / ROW:.8f};entryPerimeter=0;")
        geo = child(edge, "mxGeometry", relative=1, **{"as": "geometry"})
        points = child(geo, "Array", **{"as": "points"})
        for x, y in wire.points[1:-1]:
            child(points, "mxPoint", x=x, y=y)
    return xml_bytes(file)


def svg(diagram: Diagram) -> bytes:
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg",
                             "viewBox": f"0 0 {diagram.width} {diagram.height}",
                             "width": str(diagram.width), "height": str(diagram.height),
                             "role": "img", "aria-label": "Diagram relasi basis data"})
    child(root, "rect", x=0, y=0, width=diagram.width, height=diagram.height, fill="#f8fafc")
    defs = child(root, "defs")
    for box in diagram.boxes:
        clip = child(defs, "clipPath", id=f"clip-{box.key}")
        child(clip, "rect", x=box.x + 5, y=box.y, width=WIDTH - 10, height=box.height)

    edges = child(root, "g", id="relations")
    for wire in diagram.wires:
        source = wire.source.table
        target = wire.target.table
        description = (f"{source.name}.{source.columns[wire.source_row].name} → "
                       f"{target.name}.{target.columns[wire.target_row].name}")
        line = child(edges, "polyline", id="edge-" + wire.key, fill="none", stroke=wire.color,
                     points=" ".join(f"{x},{y}" for x, y in wire.points),
                     **{"stroke-width": 1.6,
                        "data-source": f"{wire.source.key}-c{wire.source_row}",
                        "data-target": f"{wire.target.key}-c{wire.target_row}"})
        child(line, "title").text = description
        x, y = wire.points[-1]
        base = x + (8 if wire.target_side else -8)
        child(edges, "polygon", points=f"{x},{y} {base},{y - 4} {base},{y + 4}", fill=wire.color)

    for box, labels in row_labels(diagram):
        group = child(root, "g", id=box.key)
        child(group, "rect", x=box.x, y=box.y, width=WIDTH, height=box.height, fill="#fff", stroke="#90a5ba")
        child(group, "rect", x=box.x, y=box.y, width=WIDTH, height=HEADER, fill="#20364f")
        text_group = child(group, "g", **{"clip-path": f"url(#clip-{box.key})"})
        child(text_group, "text", x=box.x + 10, y=box.y + 25, fill="#ffffff",
              **{"font-family": "sans-serif", "font-weight": "bold", "font-size": 15}).text = box.table.name
        for index, label in enumerate(labels):
            y = box.row_y(index)
            child(text_group, "rect", x=box.x + 6, y=y + 1, width=WIDTH - 12, height=ROW - 2,
                  fill="#f1f5f9" if index % 2 == 0 else "#ffffff")
            text = child(text_group, "text", id=f"{box.key}-c{index}", x=box.x + 10, y=y + 18,
                         fill="#172e42", **{"font-family": "monospace", "font-size": 12})
            text.text = label
            child(text, "title").text = label

    tags = child(root, "g", **{"font-family": "monospace", "font-size": 10, "font-weight": "bold"})
    for wire in diagram.wires:
        (x, y), (other, _) = wire.points[2:4]
        center = (x + other) // 2
        child(tags, "text", x=center, y=y + 10, fill=wire.color,
              **{"text-anchor": "middle"}).text = wire.key
    return xml_bytes(root)
