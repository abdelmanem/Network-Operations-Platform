"""HTML report exporter."""

from __future__ import annotations

import html
from dataclasses import dataclass

from backend.app.reporting.enums import DocumentNodeType, ExportFormat
from backend.app.reporting.models import DocumentNode, ExportResult, RenderedDocument


@dataclass(frozen=True, slots=True)
class HtmlExporter:
    """Export rendered documents as HTML."""

    format: ExportFormat = ExportFormat.HTML

    def export(self, document: RenderedDocument) -> ExportResult:
        body = _render_node(document.root)
        page = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(document.metadata.title)}</title>"
            "</head><body>"
            f"{body}"
            "</body></html>"
        )
        filename = f"{document.report_type.value}.html"
        return ExportResult(
            format=self.format,
            content=page.encode("utf-8"),
            mime_type="text/html",
            filename=filename,
        )


def _render_node(node: DocumentNode) -> str:
    node_type = node.node_type
    attributes = node.attributes

    if node_type == DocumentNodeType.DOCUMENT:
        title = html.escape(str(attributes.get("title", "")))
        children = "".join(_render_node(child) for child in node.children)
        report_type = html.escape(str(attributes.get("report_type", "")))
        return (
            f"<article data-report-type='{report_type}'>"
            f"<h1>{title}</h1>{children}</article>"
        )

    if node_type == DocumentNodeType.SECTION:
        title = html.escape(str(attributes.get("title", "")))
        children = "".join(_render_node(child) for child in node.children)
        return f"<section data-title='{title}'><h2>{title}</h2>{children}</section>"

    if node_type == DocumentNodeType.HEADING:
        level = int(str(attributes.get("level", 3)))
        text = html.escape(str(attributes.get("text", "")))
        return f"<h{level}>{text}</h{level}>"

    if node_type == DocumentNodeType.PARAGRAPH:
        text = html.escape(str(attributes.get("text", "")))
        return f"<p>{text}</p>"

    if node_type == DocumentNodeType.METRIC:
        key = html.escape(str(attributes.get("key", "")))
        value = html.escape(str(attributes.get("value", "")))
        return (
            f"<div class='metric' data-key='{key}'>"
            f"<span>{key}</span><strong>{value}</strong></div>"
        )

    if node_type == DocumentNodeType.KEY_VALUE:
        key = html.escape(str(attributes.get("key", "")))
        if "value" in attributes:
            value = html.escape(str(attributes.get("value", "")))
            return f"<div class='kv'><span>{key}</span><span>{value}</span></div>"
        children = "".join(_render_node(child) for child in node.children)
        return f"<div class='kv-group' data-key='{key}'>{children}</div>"

    if node_type == DocumentNodeType.LIST:
        items = attributes.get("items", ())
        if isinstance(items, tuple):
            rendered = "".join(f"<li>{html.escape(str(item))}</li>" for item in items)
            return f"<ul>{rendered}</ul>"
        return "<ul></ul>"

    if node_type == DocumentNodeType.TABLE:
        headers = attributes.get("headers", ())
        rows = attributes.get("rows", ())
        if isinstance(headers, tuple):
            header_html = "".join(
                f"<th>{html.escape(str(col))}</th>" for col in headers
            )
        else:
            header_html = ""
        body_rows: list[str] = []
        if isinstance(rows, tuple):
            for row in rows:
                if isinstance(row, tuple):
                    cells = "".join(
                        f"<td>{html.escape(str(cell))}</td>" for cell in row
                    )
                    body_rows.append(f"<tr>{cells}</tr>")
        return (
            f"<table><thead><tr>{header_html}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody></table>"
        )

    if node_type == DocumentNodeType.DIVIDER:
        return "<hr />"

    children = "".join(_render_node(child) for child in node.children)
    return children
