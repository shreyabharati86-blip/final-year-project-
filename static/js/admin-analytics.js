(function () {
  var dataNode = document.getElementById("analytics-data");
  var errorBox = document.getElementById("analytics-error");
  if (!dataNode) return;

  function showPageError() {
    if (errorBox) errorBox.classList.remove("hidden");
    document.querySelectorAll(".chart-panel").forEach(function (panel) {
      failPanel(panel, "Could not load this chart.");
    });
  }

  function setPanelState(panel, mode, message, detail) {
    var skeleton = panel.querySelector(".chart-skeleton");
    var canvas = panel.querySelector("canvas");
    var empty = panel.querySelector(".chart-empty");
    panel.classList.toggle("is-empty", mode === "empty");
    panel.classList.toggle("is-error", mode === "error");
    panel.classList.toggle("is-chart", mode === "chart");
    if (mode !== "chart") panel.style.height = "";
    if (skeleton) skeleton.classList.toggle("hidden", mode !== "loading");
    if (canvas) canvas.classList.toggle("hidden", mode !== "chart");
    if (empty) {
      empty.classList.toggle("hidden", mode !== "empty" && mode !== "error");
      var title = empty.querySelector(".chart-empty-title");
      var more = empty.querySelector(".chart-empty-detail");
      if (title) title.textContent = message || "";
      if (more) {
        var extra = mode === "empty" ? (detail || panel.getAttribute("data-empty-detail") || "") : "";
        more.textContent = extra;
        more.classList.toggle("hidden", !extra);
      }
    }
  }

  function failPanel(panel, message) {
    if (panel._chart) {
      panel._chart.destroy();
      panel._chart = null;
    }
    setPanelState(panel, "error", message || "Could not load this chart.");
  }

  function emptyPanel(panel) {
    if (panel._chart) {
      panel._chart.destroy();
      panel._chart = null;
    }
    setPanelState(panel, "empty", panel.getAttribute("data-empty") || "No data available yet.");
  }

  function hasCounts(items) {
    return Array.isArray(items) && items.some(function (item) {
      return Number(item.count) > 0;
    });
  }

  function labelsOf(items) {
    return items.map(function (item) { return item.label; });
  }

  function countsOf(items) {
    return items.map(function (item) { return Number(item.count) || 0; });
  }

  function barHeight(count) {
    return Math.max(84, count * 22 + 26);
  }

  function pluralLabel(value, singular, plural) {
    var n = Number(value) || 0;
    return n + " " + (n === 1 ? singular : plural);
  }

  var palette = ["#2563eb", "#0f172a", "#64748b", "#f97316", "#0369a1", "#334155"];
  var statusColors = {
    pending: "#f59e0b",
    accepted: "#059669",
    rejected: "#e11d48"
  };

  if (typeof Chart === "undefined") {
    showPageError();
    return;
  }

  Chart.defaults.font.family = "'Plus Jakarta Sans', 'Segoe UI', sans-serif";
  Chart.defaults.color = "#64748b";
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.padding = 8;
  Chart.defaults.layout.padding = 0;
  Chart.defaults.plugins.tooltip.backgroundColor = "#0f172a";
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation = false;
  Chart.defaults.responsive = true;

  var data;
  try {
    data = JSON.parse(dataNode.textContent);
  } catch (err) {
    showPageError();
    return;
  }

  function doughnut(panel, items, colorMap) {
    var source = items || [];
    var plotted = source.filter(function (item) {
      return Number(item.count) > 0;
    });
    if (!hasCounts(plotted)) {
      emptyPanel(panel);
      return;
    }
    var canvas = panel.querySelector("canvas");
    panel.style.height = panel.classList.contains("chart-panel-donut") ? "112px" : "168px";
    setPanelState(panel, "chart");
    var colors = plotted.map(function (item, index) {
      return (colorMap && colorMap[item.key]) || palette[index % palette.length];
    });
    var total = source.reduce(function (sum, item) {
      return sum + (Number(item.count) || 0);
    }, 0);
    panel._chart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: labelsOf(plotted),
        datasets: [{
          data: countsOf(plotted),
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: "#ffffff",
          hoverOffset: 4
        }]
      },
      options: {
        cutout: "68%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var value = Number(ctx.parsed) || 0;
                var share = total ? Math.round((value / total) * 100) : 0;
                return " " + ctx.label + ": " + value + " (" + share + "%)";
              }
            }
          }
        }
      }
    });
  }

  function bars(panel, items, color, singular, plural) {
    if (!hasCounts(items)) {
      emptyPanel(panel);
      return;
    }
    var canvas = panel.querySelector("canvas");
    var values = countsOf(items);
    var maxValue = Math.max.apply(null, values.concat([1]));
    panel.style.height = barHeight(items.length) + "px";
    setPanelState(panel, "chart");
    panel._chart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labelsOf(items),
        datasets: [{
          data: values,
          backgroundColor: color || "#2563eb",
          borderRadius: 5,
          borderSkipped: false,
          maxBarThickness: 12,
          categoryPercentage: 0.88,
          barPercentage: 0.92
        }]
      },
      options: {
        indexAxis: "y",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return " " + pluralLabel(ctx.parsed.x, singular || "item", plural || "items");
              }
            }
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            max: maxValue,
            ticks: {
              precision: 0,
              stepSize: maxValue <= 6 ? 1 : undefined,
              color: "#94a3b8"
            },
            grid: { color: "rgba(148, 163, 184, 0.16)" },
            border: { display: false }
          },
          y: {
            grid: { display: false },
            border: { display: false },
            ticks: {
              autoSkip: false,
              color: "#334155",
              font: { size: 12, weight: "600" }
            }
          }
        }
      }
    });
  }

  function drawLine(panel, series) {
    var labels = (series && series.labels) || [];
    var counts = (series && series.counts) || [];
    if (!labels.length) {
      emptyPanel(panel);
      return;
    }
    var canvas = panel.querySelector("canvas");
    if (panel._chart) {
      panel._chart.destroy();
      panel._chart = null;
    }
    panel.style.height = "200px";
    setPanelState(panel, "chart");
    panel._chart = new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Applications",
          data: counts,
          borderColor: "#2563eb",
          backgroundColor: "rgba(37, 99, 235, 0.08)",
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: labels.length > 18 ? 0 : 3.5,
          pointHoverRadius: 5,
          pointBackgroundColor: "#2563eb",
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2
        }]
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return " " + pluralLabel(ctx.parsed.y, "application", "applications");
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: "#94a3b8" },
            grid: { color: "rgba(148, 163, 184, 0.16)" },
            border: { display: false }
          },
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: { color: "#64748b", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }
          }
        }
      }
    });
  }

  function bind(name, renderer) {
    var panel = document.querySelector('.chart-panel[data-chart="' + name + '"]');
    if (!panel) return;
    try {
      renderer(panel);
    } catch (err) {
      failPanel(panel, "Could not load this chart.");
    }
  }

  bind("status", function (panel) {
    doughnut(panel, (data.applications || {}).status || [], statusColors);
  });
  bind("jobType", function (panel) {
    doughnut(panel, (data.jobs || {}).by_type || [], { job: "#2563eb", internship: "#f97316" });
  });
  bind("skills", function (panel) {
    bars(panel, (data.skills || {}).in_demand || [], "#2563eb", "job", "jobs");
  });
  bind("companyJobs", function (panel) {
    bars(panel, (data.companies || {}).by_jobs || [], "#0f172a", "posting", "postings");
  });
  bind("locations", function (panel) {
    bars(panel, (data.jobs || {}).by_location || [], "#2563eb", "job", "jobs");
  });
  bind("education", function (panel) {
    bars(panel, (data.candidates || {}).by_education || [], "#334155", "candidate", "candidates");
  });
  bind("candidateSkills", function (panel) {
    bars(panel, (data.candidates || {}).skills || [], "#2563eb", "profile", "profiles");
  });
  bind("courseSkills", function (panel) {
    bars(panel, (data.courses || {}).by_skill || [], "#2563eb", "course", "courses");
  });
  bind("courseCompanies", function (panel) {
    bars(panel, (data.courses || {}).by_company || [], "#0f172a", "course", "courses");
  });
  bind("companyApps", function (panel) {
    bars(panel, (data.companies || {}).by_applications || [], "#2563eb", "application", "applications");
  });

  var trendPanel = document.querySelector('.chart-panel[data-chart="trend"]');
  var trend = data.trend || {};
  var trendSummary = document.getElementById("trend-summary");

  function trendSeries(mode) {
    if (mode === "month" && trend.monthly && trend.monthly.labels) return trend.monthly;
    if (mode === "day" && trend.daily && trend.daily.labels) return trend.daily;
    return { labels: trend.labels || [], counts: trend.counts || [] };
  }

  function trendCaption(mode) {
    if (mode === "month") return "Grouped by month from application dates in the selected period.";
    return "Grouped by day from application dates in the selected period.";
  }

  function showTrend(mode) {
    if (!trendPanel) return;
    try {
      drawLine(trendPanel, trendSeries(mode));
      if (trendSummary && trendSeries(mode).labels.length) {
        trendSummary.textContent = "Track application activity across the selected period. " + trendCaption(mode);
      }
    } catch (err) {
      failPanel(trendPanel, "Could not load this chart.");
    }
  }

  var initialMode = trend.granularity === "month" ? "month" : "day";
  if (trendPanel) showTrend(trend.labels && trend.labels.length ? initialMode : "day");

  document.querySelectorAll("[data-trend]").forEach(function (button) {
    button.addEventListener("click", function () {
      var mode = button.getAttribute("data-trend");
      document.querySelectorAll("[data-trend]").forEach(function (item) {
        item.classList.toggle("is-active", item === button);
      });
      showTrend(mode);
    });
  });
})();
