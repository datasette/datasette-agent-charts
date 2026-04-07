import json

from datasette import hookimpl

CHART_SCRIPT_TAG = (
    '<script src="/-/static-plugins/datasette-agent-charts/datasette-chart.js"'
    ' type="module"></script>'
)

CHART_TYPES = ["barX", "barY", "line", "dot", "areaY", "waffleY"]

CHART_TYPE_SCHEMA = {
    "type": "string",
    "enum": CHART_TYPES,
    "description": "Chart type: barX (horizontal bars), barY (vertical bars), line, dot (scatter), areaY (filled area), waffleY (waffle/part-of-whole)",
}


def _build_html(config):
    config_json = json.dumps(config)
    return (
        f"{CHART_SCRIPT_TAG}\n"
        f"<datasette-chart>\n"
        f'<script type="application/json">{config_json}</script>\n'
        f"</datasette-chart>"
    )


async def _render_chart(
    datasette,
    actor,
    database,
    sql,
    chart_type,
    x,
    y,
    color=None,
    title=None,
    x_label=None,
    y_label=None,
):
    # Validate that configured columns exist in SQL results
    db = datasette.get_database(database)
    check_sql = f"with q as ({sql}) select * from q limit 0"
    result = await db.execute(check_sql)
    columns = set(result.columns)
    expected = {"x": x, "y": y}
    if color:
        expected["color"] = color
    missing = {k: v for k, v in expected.items() if v not in columns}
    if missing:
        details = ", ".join(f"{k} column '{v}' not found" for k, v in missing.items())
        return json.dumps(
            {
                "error": (
                    f"Column mismatch: {details}. "
                    f"SQL query returns columns: {sorted(columns)}"
                ),
            }
        )

    config = {
        "type": chart_type,
        "database": database,
        "sql": sql,
        "x": x,
        "y": y,
    }
    if color:
        config["color"] = color
    if title:
        config["title"] = title
    if x_label:
        config["xLabel"] = x_label
    if y_label:
        config["yLabel"] = y_label

    return json.dumps(
        {
            "_html": _build_html(config),
            "chart_type": chart_type,
            "database": database,
            "sql": sql,
        }
    )


@hookimpl
def register_agent_tools(datasette):
    from datasette_agent.tools import AgentTool

    return [
        AgentTool(
            name="render_chart",
            description=(
                "Render a chart by executing a SQL query and visualizing the results. "
                "The SQL should return rows with columns matching the x and y parameters. "
                "Supported chart types: barX (horizontal bars), barY (vertical bars), line, dot (scatter plot), "
                "areaY (filled area)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "The database name",
                    },
                    "sql": {
                        "type": "string",
                        "description": "SQL query whose results become chart data",
                    },
                    "chart_type": CHART_TYPE_SCHEMA,
                    "x": {
                        "type": "string",
                        "description": "Column name from query results for the x axis",
                    },
                    "y": {
                        "type": "string",
                        "description": "Column name from query results for the y axis",
                    },
                    "color": {
                        "type": "string",
                        "description": "Optional column name for color encoding",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional chart title",
                    },
                    "x_label": {
                        "type": "string",
                        "description": "Optional x axis label",
                    },
                    "y_label": {
                        "type": "string",
                        "description": "Optional y axis label",
                    },
                },
                "required": ["database", "sql", "chart_type", "x", "y"],
            },
            fn=_render_chart,
        ),
    ]
