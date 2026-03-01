"""
FlowWeaver Visualization Utilities

Provides export functions for rendering workflow DAGs in Mermaid.js format,
with status-based styling and configurable orientation.

Functions:
    export_mermaid  – Return a Mermaid graph string for a workflow.
    save_mermaid    – Write the Mermaid string to a file.
    view_mermaid    – Open an interactive Mermaid diagram in the default browser.
"""

import logging
import re
import tempfile
import webbrowser
from pathlib import Path

from flowweaver.core import TaskStatus, Workflow

logger = logging.getLogger(__name__)

# Mermaid classDef colour definitions keyed by TaskStatus.
_STATUS_STYLES: dict[TaskStatus, tuple[str, str]] = {
    TaskStatus.COMPLETED: ("completed", "fill:#28a745,stroke:#1e7e34,color:#fff"),
    TaskStatus.FAILED:    ("failed",    "fill:#dc3545,stroke:#bd2130,color:#fff"),
    TaskStatus.RUNNING:   ("running",   "fill:#fd7e14,stroke:#e8590c,color:#fff"),
    TaskStatus.PENDING:   ("pending",   "fill:#6c757d,stroke:#545b62,color:#fff"),
}

_VALID_ORIENTATIONS = {"TD", "TB", "BT", "LR", "RL"}


def _sanitize_id(name: str) -> str:
    """Convert an arbitrary task name into a valid Mermaid node ID.

    Mermaid node IDs must contain only alphanumeric characters and underscores.
    All other characters are replaced with underscores, and leading digits are
    prefixed with an underscore to guarantee a valid identifier.

    Args:
        name: The original task name.

    Returns:
        A sanitized string safe for use as a Mermaid node ID.
    """
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized or "_unnamed"


def export_mermaid(workflow: Workflow, orientation: str = "TD") -> str:
    """Export a workflow DAG as a Mermaid.js graph definition string.

    Generates a complete ``graph`` block including:
    * Node declarations with human-readable labels.
    * Directed edges derived from the workflow's dependency map.
    * ``classDef`` directives that colour nodes by their current
      :class:`~flowweaver.core.TaskStatus`.

    Args:
        workflow: The :class:`~flowweaver.core.Workflow` instance to export.
        orientation: Graph direction — ``"TD"`` (top-down, default), ``"LR"``
            (left-to-right), ``"BT"`` (bottom-to-top), or ``"RL"``
            (right-to-left).

    Returns:
        A multi-line string containing the full Mermaid graph definition.

    Raises:
        ValueError: If *orientation* is not a recognised Mermaid direction.

    Example::

        from flowweaver.utils import export_mermaid
        print(export_mermaid(wf, orientation="LR"))
    """
    orientation = orientation.upper()
    if orientation not in _VALID_ORIENTATIONS:
        raise ValueError(
            f"Invalid orientation '{orientation}'. "
            f"Must be one of {sorted(_VALID_ORIENTATIONS)}."
        )

    tasks = workflow.get_all_tasks()
    if not tasks:
        return f"graph {orientation}\n"

    lines: list[str] = [f"graph {orientation}"]

    # --- Node declarations ---------------------------------------------------
    node_ids: dict[str, str] = {}  # original name -> sanitized ID
    for name, task_obj in tasks.items():
        node_id = _sanitize_id(name)
        node_ids[name] = node_id
        lines.append(f"    {node_id}[{name}]")

    # --- Edge declarations ----------------------------------------------------
    for name in tasks:
        deps = workflow.get_dependencies(name)
        target_id = node_ids[name]
        for dep_name in deps:
            source_id = node_ids.get(dep_name)
            if source_id is None:
                logger.warning(
                    "Dependency '%s' of task '%s' is not registered in the "
                    "workflow; skipping edge.",
                    dep_name,
                    name,
                )
                continue
            lines.append(f"    {source_id} --> {target_id}")

    # --- Class definitions & assignments --------------------------------------
    lines.append("")
    for status, (class_name, style) in _STATUS_STYLES.items():
        lines.append(f"    classDef {class_name} {style}")

    # Group tasks by status for compact class assignments
    status_groups: dict[str, list[str]] = {}
    for name, task_obj in tasks.items():
        class_name = _STATUS_STYLES.get(task_obj.status, _STATUS_STYLES[TaskStatus.PENDING])[0]
        status_groups.setdefault(class_name, []).append(node_ids[name])

    for class_name, ids in status_groups.items():
        lines.append(f"    class {','.join(ids)} {class_name}")

    # Trailing newline for clean file output
    lines.append("")
    return "\n".join(lines)


def save_mermaid(
    workflow: Workflow,
    filepath: str,
    orientation: str = "TD",
) -> None:
    """Export a workflow to Mermaid.js format and write it to a file.

    This is a convenience wrapper around :func:`export_mermaid` that handles
    file I/O and basic error reporting.

    Args:
        workflow: The :class:`~flowweaver.core.Workflow` instance to export.
        filepath: Destination file path (will be created or overwritten).
        orientation: Graph direction forwarded to :func:`export_mermaid`.

    Raises:
        ValueError: If *orientation* is invalid (propagated from
            :func:`export_mermaid`).
        OSError: If the file cannot be written (e.g. permission denied,
            invalid path).
    """
    mermaid_str = export_mermaid(workflow, orientation=orientation)
    try:
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(mermaid_str)
        logger.info("Mermaid diagram saved to '%s'.", filepath)
        print(f"Mermaid diagram saved to '{filepath}'.")
    except OSError as exc:
        logger.error("Failed to write Mermaid diagram to '%s': %s", filepath, exc)
        raise


# ---------------------------------------------------------------------------
# HTML boilerplate for the interactive browser viewer
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} – FlowWeaver Diagram</title>
  <style>
    body {{
      margin: 0;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: #1e1e2e;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    #container {{
      background: #fff;
      border-radius: 12px;
      padding: 2rem 3rem;
      box-shadow: 0 8px 30px rgba(0,0,0,.3);
      max-width: 1600px;
      width: 95vw;
      overflow-x: auto;
    }}
    h3 {{
      text-align: center;
      color: #333;
      margin-bottom: 1.5rem;
    }}
  </style>
</head>
<body>
  <div id="container">
    <h3>{title}</h3>
    <pre class="mermaid">
{mermaid}
    </pre>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({{
    startOnLoad: true,
    theme: "default",
    maxTextSize: 1000000,
    maxNodes: 20000,
    securityLevel: "loose"
  }});</script>
</body>
</html>
"""


def view_mermaid(
    workflow: Workflow,
    orientation: str = "TD",
) -> Path:
    """Render the workflow diagram in the default web browser.

    Creates a self-contained temporary HTML file that loads *mermaid.js*
    from the jsDelivr CDN and renders the graph client-side.  The file is
    opened automatically via :func:`webbrowser.open`.

    The Mermaid configuration uses ``maxTextSize: 1_000_000`` and
    ``maxNodes: 20_000`` so DAGs with 5 000+ tasks render without
    hitting the default text-size limit.

    Args:
        workflow: The :class:`~flowweaver.core.Workflow` instance to visualise.
        orientation: Graph direction forwarded to :func:`export_mermaid`.

    Returns:
        :class:`~pathlib.Path` to the temporary HTML file (useful for tests
        or further processing).

    Raises:
        ValueError: If *orientation* is invalid (propagated from
            :func:`export_mermaid`).
    """
    mermaid_str = export_mermaid(workflow, orientation=orientation)
    title = workflow.name or "Workflow"

    html = _HTML_TEMPLATE.format(title=title, mermaid=mermaid_str)

    # Write to a temp file that persists until the OS cleans it up
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        prefix="flowweaver_",
        delete=False,
        encoding="utf-8",
    )
    tmp.write(html)
    tmp.close()

    tmp_path = Path(tmp.name)
    webbrowser.open(tmp_path.as_uri())
    logger.info("Opened Mermaid diagram in browser: %s", tmp_path)
    print(f"Mermaid diagram opened in browser ({tmp_path.name}).")
    return tmp_path
