import json

from datasette import hookimpl
from datasette.resources import DatabaseResource

CHART_SCRIPT_TAG = (
    '<script src="/-/static-plugins/datasette-agent-charts/datasette-chart.js"'
    ' type="module"></script>'
)

CHART_TYPES = ["barX", "barY", "line", "dot", "areaY", "waffleY"]
DATE_INTERVALS = [
    "millisecond",
    "second",
    "minute",
    "hour",
    "day",
    "week",
    "month",
    "year",
]

CHART_TYPE_SCHEMA = {
    "type": "string",
    "enum": CHART_TYPES,
    "description": "Chart type: barX (horizontal bars), barY (vertical bars), line, dot (scatter), areaY (filled area), waffleY (waffle/part-of-whole)",
}

DATE_INTERVAL_SCHEMA = {
    "type": "string",
    "enum": DATE_INTERVALS,
    "description": "Optional UTC date interval for a parsed date axis, such as month or day",
}


def _build_html(config):
    config_json = json.dumps(config)
    return (
        f"{CHART_SCRIPT_TAG}\n"
        f"<datasette-chart>\n"
        f'<script type="application/json">{config_json}</script>\n'
        f"</datasette-chart>"
    )


def _date_config_options(
    x_date_format=None,
    y_date_format=None,
    x_date_interval=None,
    y_date_interval=None,
    x_date_tick_format=None,
    y_date_tick_format=None,
    x_date_tick_every=None,
    y_date_tick_every=None,
):
    config = {}
    raw_options = {
        "x": {
            "format": x_date_format,
            "interval": x_date_interval,
            "tick_format": x_date_tick_format,
            "tick_every": x_date_tick_every,
        },
        "y": {
            "format": y_date_format,
            "interval": y_date_interval,
            "tick_format": y_date_tick_format,
            "tick_every": y_date_tick_every,
        },
    }
    for axis, options in raw_options.items():
        date_format = options["format"]
        interval = options["interval"]
        tick_format = options["tick_format"]
        tick_every = options["tick_every"]
        has_axis_option = any(
            value is not None for value in (interval, tick_format, tick_every)
        )
        if has_axis_option and not date_format:
            return None, f"{axis}_date_format is required for {axis} date axis options"
        if date_format:
            config[f"{axis}DateFormat"] = date_format
        if interval:
            if interval not in DATE_INTERVALS:
                return (
                    None,
                    f"{axis}_date_interval must be one of: {', '.join(DATE_INTERVALS)}",
                )
            config[f"{axis}DateInterval"] = interval
        if tick_format:
            config[f"{axis}DateTickFormat"] = tick_format
        if tick_every is not None:
            if isinstance(tick_every, bool):
                return None, f"{axis}_date_tick_every must be a positive integer"
            try:
                tick_every = int(tick_every)
            except (TypeError, ValueError):
                return None, f"{axis}_date_tick_every must be a positive integer"
            if tick_every < 1:
                return None, f"{axis}_date_tick_every must be a positive integer"
            config[f"{axis}DateTickEvery"] = tick_every
    return config, None


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
    x_date_format=None,
    y_date_format=None,
    x_date_interval=None,
    y_date_interval=None,
    x_date_tick_format=None,
    y_date_tick_format=None,
    x_date_tick_every=None,
    y_date_tick_every=None,
):
    date_config, date_config_error = _date_config_options(
        x_date_format=x_date_format,
        y_date_format=y_date_format,
        x_date_interval=x_date_interval,
        y_date_interval=y_date_interval,
        x_date_tick_format=x_date_tick_format,
        y_date_tick_format=y_date_tick_format,
        x_date_tick_every=x_date_tick_every,
        y_date_tick_every=y_date_tick_every,
    )
    if date_config_error:
        return json.dumps({"error": date_config_error})

    # The tool runs arbitrary SQL, so require the actor's execute-sql permission
    if not await datasette.allowed(
        action="execute-sql",
        resource=DatabaseResource(database=database),
        actor=actor,
    ):
        return json.dumps(
            {
                "error": (
                    f"Permission denied: you do not have permission to "
                    f"execute SQL against the '{database}' database."
                )
            }
        )

    # Validate that configured columns exist in SQL results
    db = datasette.get_database(database)
    check_sql = f"with q as ({sql}) select * from q limit 0"
    try:
        result = await db.execute(check_sql)
    except Exception as e:
        return json.dumps({"error": f"SQL error: {e}"})
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
        "queryUrl": datasette.urls.database(database) + "/-/query",
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
    config.update(date_config)

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
                "Use x_date_format or y_date_format for date strings such as YYYYMM months. "
                "Supported chart types: barX (horizontal bars), barY (vertical bars), line, dot (scatter plot), "
                "areaY (filled area), waffleY (waffle/part-of-whole)."
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
                    "x_date_format": {
                        "type": "string",
                        "description": (
                            "Optional d3.utcParse pattern for parsing the x column as "
                            "a UTC date, e.g. %Y%m or %Y-%m"
                        ),
                    },
                    "y_date_format": {
                        "type": "string",
                        "description": (
                            "Optional d3.utcParse pattern for parsing the y column as "
                            "a UTC date"
                        ),
                    },
                    "x_date_interval": DATE_INTERVAL_SCHEMA,
                    "y_date_interval": DATE_INTERVAL_SCHEMA,
                    "x_date_tick_format": {
                        "type": "string",
                        "description": (
                            "Optional d3.utcFormat pattern for x-axis tick labels, "
                            "e.g. %Y-%m"
                        ),
                    },
                    "y_date_tick_format": {
                        "type": "string",
                        "description": "Optional d3.utcFormat pattern for y-axis tick labels",
                    },
                    "x_date_tick_every": {
                        "type": "integer",
                        "minimum": 1,
                        "description": (
                            "Optional tick interval step for the parsed x date axis, "
                            "used with x_date_interval"
                        ),
                    },
                    "y_date_tick_every": {
                        "type": "integer",
                        "minimum": 1,
                        "description": (
                            "Optional tick interval step for the parsed y date axis, "
                            "used with y_date_interval"
                        ),
                    },
                },
                "required": ["database", "sql", "chart_type", "x", "y"],
            },
            fn=_render_chart,
        ),
    ]
