import json

from datasette.app import Datasette
import pytest

from datasette_agent_charts import (
    CHART_SCRIPT_TAG,
    CHART_TYPES,
    CHART_TYPE_SCHEMA,
    _build_html,
    _render_chart,
)


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
    assert "datasette-agent-charts" in installed_plugins


def test_chart_type_schema():
    assert CHART_TYPE_SCHEMA["type"] == "string"
    assert CHART_TYPE_SCHEMA["enum"] == CHART_TYPES
    assert set(CHART_TYPE_SCHEMA["enum"]) == {
        "barX", "barY", "line", "dot", "areaY", "waffleY",
    }


def test_build_html():
    config = {"type": "barY", "database": "test", "sql": "select 1", "x": "a", "y": "b"}
    html = _build_html(config)
    assert CHART_SCRIPT_TAG in html
    assert "<datasette-chart>" in html
    assert "</datasette-chart>" in html
    assert '<script type="application/json">' in html
    assert json.dumps(config) in html


def test_build_html_config_json_round_trips():
    config = {"type": "line", "database": "db", "sql": "select x, y from t", "x": "x", "y": "y", "color": "c"}
    html = _build_html(config)
    # Extract the JSON between the application/json script tags
    start = html.index('<script type="application/json">') + len('<script type="application/json">')
    end = html.index("</script>", start)
    parsed = json.loads(html[start:end])
    assert parsed == config


@pytest.mark.asyncio
async def test_render_chart_minimal():
    result = await _render_chart(
        datasette=None,
        actor=None,
        database="mydb",
        sql="select name, count from t",
        chart_type="barY",
        x="name",
        y="count",
    )
    data = json.loads(result)
    assert data["chart_type"] == "barY"
    assert data["database"] == "mydb"
    assert data["sql"] == "select name, count from t"
    assert "_html" in data

    # Verify the embedded config has no optional keys
    html = data["_html"]
    start = html.index('<script type="application/json">') + len('<script type="application/json">')
    end = html.index("</script>", start)
    embedded_config = json.loads(html[start:end])
    assert embedded_config == {
        "type": "barY",
        "database": "mydb",
        "sql": "select name, count from t",
        "x": "name",
        "y": "count",
    }


@pytest.mark.asyncio
async def test_render_chart_all_options():
    result = await _render_chart(
        datasette=None,
        actor=None,
        database="mydb",
        sql="select a, b, c from t",
        chart_type="dot",
        x="a",
        y="b",
        color="c",
        title="My Chart",
        x_label="X Axis",
        y_label="Y Axis",
    )
    data = json.loads(result)
    assert data["chart_type"] == "dot"

    html = data["_html"]
    start = html.index('<script type="application/json">') + len('<script type="application/json">')
    end = html.index("</script>", start)
    embedded_config = json.loads(html[start:end])
    assert embedded_config["color"] == "c"
    assert embedded_config["title"] == "My Chart"
    assert embedded_config["xLabel"] == "X Axis"
    assert embedded_config["yLabel"] == "Y Axis"


@pytest.mark.asyncio
async def test_render_chart_html_contains_script_and_element():
    result = await _render_chart(
        datasette=None,
        actor=None,
        database="db",
        sql="select 1",
        chart_type="line",
        x="x",
        y="y",
    )
    data = json.loads(result)
    assert CHART_SCRIPT_TAG in data["_html"]
    assert "<datasette-chart>" in data["_html"]
    assert "</datasette-chart>" in data["_html"]
