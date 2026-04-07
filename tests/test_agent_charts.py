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
        "barX",
        "barY",
        "line",
        "dot",
        "areaY",
        "waffleY",
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
    config = {
        "type": "line",
        "database": "db",
        "sql": "select x, y from t",
        "x": "x",
        "y": "y",
        "color": "c",
    }
    html = _build_html(config)
    # Extract the JSON between the application/json script tags
    start = html.index('<script type="application/json">') + len(
        '<script type="application/json">'
    )
    end = html.index("</script>", start)
    parsed = json.loads(html[start:end])
    assert parsed == config


@pytest.mark.asyncio
async def test_render_chart_minimal(datasette_db):
    result = await _render_chart(
        datasette=datasette_db,
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
    start = html.index('<script type="application/json">') + len(
        '<script type="application/json">'
    )
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
async def test_render_chart_all_options(datasette_db):
    result = await _render_chart(
        datasette=datasette_db,
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
    start = html.index('<script type="application/json">') + len(
        '<script type="application/json">'
    )
    end = html.index("</script>", start)
    embedded_config = json.loads(html[start:end])
    assert embedded_config["color"] == "c"
    assert embedded_config["title"] == "My Chart"
    assert embedded_config["xLabel"] == "X Axis"
    assert embedded_config["yLabel"] == "Y Axis"


@pytest.mark.asyncio
async def test_render_chart_html_contains_script_and_element(datasette_db):
    result = await _render_chart(
        datasette=datasette_db,
        actor=None,
        database="mydb",
        sql="select x, y from t",
        chart_type="line",
        x="x",
        y="y",
    )
    data = json.loads(result)
    assert CHART_SCRIPT_TAG in data["_html"]
    assert "<datasette-chart>" in data["_html"]
    assert "</datasette-chart>" in data["_html"]


@pytest.fixture
def datasette_db(tmp_path):
    import sqlite3

    db_path = tmp_path / "mydb.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "create table t (name text, count integer, a real, b real, c text, x real, y real)"
    )
    conn.execute("insert into t values ('foo', 1, 1.0, 2.0, 'red', 10, 20)")
    conn.close()
    return Datasette([str(db_path)])


@pytest.fixture
def datasette_with_trees(tmp_path):
    import sqlite3

    db_path = tmp_path / "trees.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("create table trees (Latitude real, Longitude real, Species text)")
    conn.execute("insert into trees values (37.75, -122.4, 'Oak')")
    conn.close()
    return Datasette([str(db_path)])


@pytest.mark.asyncio
async def test_render_chart_validates_columns(datasette_with_trees):
    """Columns in x/y/color must match actual SQL result columns."""
    # SQL aliases Latitude->x, Longitude->y, but config says Latitude/Longitude
    result = await _render_chart(
        datasette=datasette_with_trees,
        actor=None,
        database="trees",
        sql="SELECT Latitude as x, Longitude as y FROM trees",
        chart_type="dot",
        x="Latitude",
        y="Longitude",
    )
    data = json.loads(result)
    assert "_html" not in data
    assert data["error"] == (
        "Column mismatch: x column 'Latitude' not found, "
        "y column 'Longitude' not found. "
        "SQL query returns columns: ['x', 'y']"
    )


@pytest.mark.asyncio
async def test_render_chart_validates_color_column(datasette_with_trees):
    """Color column must also exist in SQL results."""
    result = await _render_chart(
        datasette=datasette_with_trees,
        actor=None,
        database="trees",
        sql="SELECT Latitude as x, Longitude as y FROM trees",
        chart_type="dot",
        x="x",
        y="y",
        color="Species",
    )
    data = json.loads(result)
    assert "_html" not in data
    assert data["error"] == (
        "Column mismatch: color column 'Species' not found. "
        "SQL query returns columns: ['x', 'y']"
    )


@pytest.mark.asyncio
async def test_render_chart_valid_columns_pass(datasette_with_trees):
    """Correct column names should produce _html with no error."""
    result = await _render_chart(
        datasette=datasette_with_trees,
        actor=None,
        database="trees",
        sql="SELECT Latitude as x, Longitude as y FROM trees",
        chart_type="dot",
        x="x",
        y="y",
    )
    data = json.loads(result)
    assert "_html" in data
    assert "error" not in data
