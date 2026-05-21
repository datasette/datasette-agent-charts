const PLOT_MODULE_URL =
  "https://esm.sh/@observablehq/plot@0.6.17/es2022/plot.bundle.mjs";
const D3_TIME_FORMAT_MODULE_URL =
  "https://esm.sh/d3-time-format@4.1.0/es2022/d3-time-format.bundle.mjs";
const D3_TIME_MODULE_URL =
  "https://esm.sh/d3-time@3.1.0/es2022/d3-time.bundle.mjs";

let plotPromise = null;
function loadPlot() {
  if (!plotPromise) {
    plotPromise = import(PLOT_MODULE_URL);
  }
  return plotPromise;
}

let d3TimePromise = null;
function loadD3Time() {
  if (!d3TimePromise) {
    d3TimePromise = Promise.all([
      import(D3_TIME_FORMAT_MODULE_URL),
      import(D3_TIME_MODULE_URL),
    ]).then(([timeFormat, time]) => ({ ...timeFormat, ...time }));
  }
  return d3TimePromise;
}

const UTC_INTERVALS = {
  millisecond: "utcMillisecond",
  second: "utcSecond",
  minute: "utcMinute",
  hour: "utcHour",
  day: "utcDay",
  week: "utcWeek",
  month: "utcMonth",
  year: "utcYear",
};

function hasDateAxis(config) {
  return Boolean(config.xDateFormat || config.yDateFormat);
}

function patternHasAny(format, directives) {
  return directives.some((directive) => format.includes(directive));
}

function inferDateInterval(format) {
  if (patternHasAny(format, ["%L", "%f"])) return "millisecond";
  if (patternHasAny(format, ["%S"])) return "second";
  if (patternHasAny(format, ["%M"])) return "minute";
  if (patternHasAny(format, ["%H", "%I", "%p"])) return "hour";
  if (patternHasAny(format, ["%d", "%e", "%j"])) return "day";
  if (patternHasAny(format, ["%U", "%W", "%V"])) return "week";
  if (patternHasAny(format, ["%m", "%b", "%B"])) return "month";
  if (patternHasAny(format, ["%Y", "%y"])) return "year";
  return null;
}

function defaultTickFormat(interval) {
  switch (interval) {
    case "year":
      return "%Y";
    case "month":
      return "%Y-%m";
    case "week":
    case "day":
      return "%Y-%m-%d";
    case "hour":
    case "minute":
      return "%Y-%m-%d %H:%M";
    case "second":
      return "%H:%M:%S";
    case "millisecond":
      return "%H:%M:%S.%L";
    default:
      return null;
  }
}

function utcInterval(d3, interval) {
  const name = UTC_INTERVALS[interval];
  return name ? d3[name] : null;
}

function uniqueColumnName(base, used) {
  let name = base;
  let suffix = 2;
  while (used.has(name)) {
    name = `${base}_${suffix}`;
    suffix += 1;
  }
  used.add(name);
  return name;
}

function applyDateAxes(data, config, d3) {
  if (!d3 || !hasDateAxis(config)) {
    return { data, axes: {} };
  }

  const usedColumns = new Set(Object.keys(data[0] || {}));
  const axes = {};

  for (const axis of ["x", "y"]) {
    const format = config[`${axis}DateFormat`];
    if (!format) continue;

    const column = config[axis];
    const parser = d3.utcParse(format);
    const parsedColumn = uniqueColumnName(`_${column}_${axis}_date`, usedColumns);
    axes[axis] = {
      column,
      format,
      parser,
      parsedColumn,
      interval: config[`${axis}DateInterval`] || inferDateInterval(format),
      tickFormat: config[`${axis}DateTickFormat`],
      tickEvery: config[`${axis}DateTickEvery`],
    };
  }

  if (!Object.keys(axes).length) {
    return { data, axes };
  }

  const parsedData = data.map((row) => {
    const next = { ...row };
    for (const axis of Object.keys(axes)) {
      const dateAxis = axes[axis];
      const value = row[dateAxis.column];
      next[dateAxis.parsedColumn] =
        value == null || value === ""
          ? null
          : value instanceof Date
            ? value
            : dateAxis.parser(String(value));
    }
    return next;
  });

  return { data: parsedData, axes };
}

function axisOptions(label, dateAxis, d3) {
  const options = {};
  if (label) {
    options.label = label;
  } else if (dateAxis) {
    options.label = dateAxis.column;
  }

  if (dateAxis && d3) {
    const interval = dateAxis.interval;
    const tickEvery = Number(dateAxis.tickEvery);
    if (interval && Number.isInteger(tickEvery) && tickEvery > 0) {
      const intervalFunction = utcInterval(d3, interval);
      if (intervalFunction && intervalFunction.every) {
        options.ticks = intervalFunction.every(tickEvery);
      }
    }

    const tickFormat = dateAxis.tickFormat || defaultTickFormat(interval);
    if (tickFormat) {
      options.tickFormat = d3.utcFormat(tickFormat);
    }
  }

  return Object.keys(options).length ? options : null;
}

function sqlQueryUrl(queryUrl, sql) {
  const url = new URL(queryUrl, window.location.href);
  url.searchParams.set("sql", sql);
  return url.href;
}

function createSqlEditLink(queryUrl, sql) {
  const editLink = document.createElement("p");
  editLink.className = "agent-sql-edit-link";
  const link = document.createElement("a");
  link.href = sqlQueryUrl(queryUrl, sql);
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "View SQL query";
  editLink.appendChild(link);
  return editLink;
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

    const { database, sql, queryUrl } = config;
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

    const [Plot, d3] = await Promise.all([
      loadPlot(),
      hasDateAxis(config) ? loadD3Time() : Promise.resolve(null),
    ]);
    this.textContent = "";
    const chart = this.buildChart(Plot, d3, config, data);
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

    // Match the Datasette Agent SQL action shown below table results.
    if (queryUrl && sql) {
      this.appendChild(createSqlEditLink(queryUrl, sql));
    }
  }

  buildChart(Plot, d3, config, data) {
    const { type, x, y, color, title, xLabel, yLabel } = config;
    const { data: plotData, axes } = applyDateAxes(data, config, d3);

    // tip: true adds an interactive tooltip showing each point's channel values
    const markOptions = {
      x: axes.x ? axes.x.parsedColumn : x,
      y: axes.y ? axes.y.parsedColumn : y,
      tip: true,
    };

    // For bar/waffle charts the value column is shaded when no color is given
    const valueColumn = { barX: x, barY: y, waffleY: y };

    let colorScheme = null;
    if (color) {
      // Explicit color column: stroke for line/dot marks, fill for the rest
      if (type === "line" || type === "dot") {
        markOptions.stroke = color;
      } else {
        markOptions.fill = color;
      }
      // Text-valued color columns read best with a categorical scheme
      const sample = plotData.find((row) => row[color] != null);
      if (sample && typeof sample[color] === "string") {
        colorScheme = "observable10";
      }
    } else if (valueColumn[type]) {
      // No color column: shade each bar by its own magnitude
      markOptions.fill = valueColumn[type];
      colorScheme = "blues";
    } else if (type === "line" || type === "dot") {
      markOptions.stroke = "#1e3a5f";
    } else {
      markOptions.fill = "#1e3a5f";
    }

    const marks = [];
    switch (type) {
      case "barX":
        if (axes.y && axes.y.interval) {
          marks.push(
            Plot.rectX(plotData, {
              ...markOptions,
              interval: axes.y.interval,
              inset: 0.5,
            }),
          );
        } else {
          marks.push(Plot.barX(plotData, markOptions));
        }
        marks.push(Plot.ruleX([0]));
        break;
      case "barY":
        if (axes.x && axes.x.interval) {
          marks.push(
            Plot.rectY(plotData, {
              ...markOptions,
              interval: axes.x.interval,
              inset: 0.5,
            }),
          );
        } else {
          marks.push(Plot.barY(plotData, markOptions));
        }
        marks.push(Plot.ruleY([0]));
        break;
      case "line":
        marks.push(Plot.line(plotData, markOptions));
        break;
      case "dot":
        marks.push(Plot.dot(plotData, markOptions));
        break;
      case "areaY":
        marks.push(Plot.areaY(plotData, markOptions));
        marks.push(Plot.ruleY([0]));
        break;
      case "waffleY":
        marks.push(Plot.waffleY(plotData, markOptions));
        break;
      default:
        this.textContent = "Unknown chart type: " + type;
        return null;
    }

    const plotOptions = { marks };
    if (colorScheme) plotOptions.color = { scheme: colorScheme };
    const xOptions = axisOptions(xLabel, axes.x, d3);
    const yOptions = axisOptions(yLabel, axes.y, d3);
    if (xOptions) plotOptions.x = xOptions;
    if (yOptions) plotOptions.y = yOptions;
    if (axes.x) plotOptions.marginBottom = 45;
    if (title) plotOptions.title = title;

    return Plot.plot(plotOptions);
  }
}

if (!customElements.get("datasette-chart")) {
  customElements.define("datasette-chart", DatasetteChart);
}
