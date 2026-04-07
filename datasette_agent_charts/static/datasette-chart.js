const PLOT_MODULE_URL =
  "https://esm.sh/@observablehq/plot@0.6.17/es2022/plot.bundle.mjs";

let plotPromise = null;
function loadPlot() {
  if (!plotPromise) {
    plotPromise = import(PLOT_MODULE_URL);
  }
  return plotPromise;
}

class DatasetteChart extends HTMLElement {
  async connectedCallback() {
    // Grab the config script before modifying DOM, since textContent wipes children
    let scriptEl = this.querySelector('script[type="application/json"]');

    if (!scriptEl) {
      // Wait a frame in case children aren't parsed yet (innerHTML insertion)
      await new Promise((r) => requestAnimationFrame(r));
      scriptEl = this.querySelector('script[type="application/json"]');
    }

    this.textContent = "Loading chart\u2026";
    if (!scriptEl) {
      this.textContent = "Error: no chart configuration found";
      return;
    }

    let config;
    try {
      config = JSON.parse(scriptEl.textContent);
    } catch (e) {
      this.textContent = "Error parsing chart config: " + e.message;
      return;
    }

    const { database, sql } = config;
    if (!database || !sql) {
      this.textContent = "Error: database and sql are required";
      return;
    }

    let data;
    try {
      const url =
        "/" +
        encodeURIComponent(database) +
        "/-/query.json?sql=" +
        encodeURIComponent(sql) +
        "&_shape=array";
      const resp = await fetch(url);
      if (!resp.ok) {
        const text = await resp.text();
        this.textContent = "Query error: " + text;
        return;
      }
      data = await resp.json();
    } catch (e) {
      this.textContent = "Fetch error: " + e.message;
      return;
    }

    const Plot = await loadPlot();
    this.textContent = "";
    const chart = this.buildChart(Plot, config, data);
    if (chart) {
      // Show Observable Plot warnings as visible text
      (() => {
        let warn = chart.querySelector("[aria-description=warning]");
        if (warn) {
          let title = warn.querySelector("title");
          if (title) {
            let div = document.createElement("div");
            div.style.cssText = "background:#fff3cd;border:1px solid #ffc107;padding:8px;margin-top:8px;border-radius:4px;font-size:0.85em";
            div.textContent = "Plot warning: " + title.textContent;
            chart.appendChild(div);
          }
          warn.remove();
        }
      })();
      this.appendChild(chart);
    }

    // Show the SQL query in a collapsible details element
    if (sql) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "SQL query";
      details.appendChild(summary);
      const pre = document.createElement("pre");
      pre.textContent = sql;
      details.appendChild(pre);
      this.appendChild(details);
    }
  }

  buildChart(Plot, config, data) {
    const { type, x, y, color, title, width, height, xLabel, yLabel } = config;

    const markOptions = { x, y };

    // Color encoding: fill for bar/area, stroke for line/dot
    if (color) {
      if (type === "line" || type === "dot") {
        markOptions.stroke = color;
      } else {
        markOptions.fill = color;
      }
    } else {
      if (type === "line" || type === "dot") {
        markOptions.stroke = "#1e3a5f";
      } else {
        markOptions.fill = "#1e3a5f";
      }
    }

    const marks = [];
    switch (type) {
      case "barX":
        marks.push(Plot.barX(data, markOptions));
        marks.push(Plot.ruleX([0]));
        break;
      case "barY":
        marks.push(Plot.barY(data, markOptions));
        marks.push(Plot.ruleY([0]));
        break;
      case "line":
        marks.push(Plot.line(data, markOptions));
        break;
      case "dot":
        marks.push(Plot.dot(data, markOptions));
        break;
      case "areaY":
        marks.push(Plot.areaY(data, markOptions));
        marks.push(Plot.ruleY([0]));
        break;
      case "waffleY":
        marks.push(Plot.waffleY(data, markOptions));
        break;
      default:
        this.textContent = "Unknown chart type: " + type;
        return null;
    }

    const plotOptions = { marks };
    if (width) plotOptions.width = width;
    if (height) plotOptions.height = height;
    if (xLabel) plotOptions.x = { label: xLabel };
    if (yLabel) plotOptions.y = { label: yLabel };
    if (title) plotOptions.title = title;

    return Plot.plot(plotOptions);
  }
}

if (!customElements.get("datasette-chart")) {
  customElements.define("datasette-chart", DatasetteChart);
}
