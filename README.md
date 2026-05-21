# datasette-agent-charts

[![PyPI](https://img.shields.io/pypi/v/datasette-agent-charts.svg)](https://pypi.org/project/datasette-agent-charts/)
[![Changelog](https://img.shields.io/github/v/release/datasette/datasette-agent-charts?include_prereleases&label=changelog)](https://github.com/datasette/datasette-agent-charts/releases)
[![Tests](https://github.com/datasette/datasette-agent-charts/actions/workflows/test.yml/badge.svg)](https://github.com/datasette/datasette-agent-charts/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/datasette/datasette-agent-charts/blob/main/LICENSE)

Observable Plot charts for [Datasette agent](https://github.com/datasette/datasette-agent).

## Installation

Install this plugin in the same environment as Datasette.
```bash
datasette install datasette-agent-charts
```
## Usage

This plugin adds a `render_chart` tool to [Datasette Agent](https://github.com/datasette/datasette-agent) that can generate charts from SQL query results using [Observable Plot](https://observablehq.com/plot/).

Try prompts like this one, adapted to your available tables:

> `Draw a bar chart of downloads over time`

## Tool definition

The `render_chart` tool accepts the following parameters:

- **database** — the database to query
- **sql** — SQL query whose results become chart data
- **chart_type** — one of `barX`, `barY`, `line`, `dot`, `areaY`, `waffleY`
- **x** — column name for the x axis
- **y** — column name for the y axis
- **color** — (optional) column name for color encoding
- **title** — (optional) chart title
- **x_label** — (optional) x axis label
- **y_label** — (optional) y axis label
- **x_date_format** — (optional) parse the x column as a UTC date using a `d3.utcParse` pattern, for example `%Y%m` or `%Y-%m`
- **y_date_format** — (optional) parse the y column as a UTC date
- **x_date_interval** — (optional) date interval for parsed x-axis bars and ticks: `millisecond`, `second`, `minute`, `hour`, `day`, `week`, `month`, or `year`
- **y_date_interval** — (optional) date interval for parsed y-axis bars and ticks
- **x_date_tick_format** — (optional) format parsed x-axis tick labels using a `d3.utcFormat` pattern, for example `%Y-%m`
- **y_date_tick_format** — (optional) format parsed y-axis tick labels
- **x_date_tick_every** — (optional) show parsed x-axis ticks every N date intervals
- **y_date_tick_every** — (optional) show parsed y-axis ticks every N date intervals

For example, if a SQL query returns monthly values as `202401`, use:

```json
{
  "chart_type": "barY",
  "x": "month",
  "y": "count",
  "x_date_format": "%Y%m",
  "x_date_interval": "month",
  "x_date_tick_format": "%Y-%m",
  "x_date_tick_every": 3
}
```

## Development

To set up this plugin locally, first checkout the code. You can confirm it is available like this:
```bash
cd datasette-agent-charts
# Confirm the plugin is visible
uv run datasette plugins
```
To run the tests:
```bash
uv run pytest
```
