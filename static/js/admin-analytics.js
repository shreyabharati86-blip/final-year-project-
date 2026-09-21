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

  function setPanelState(panel, mode, message) {
    var skeleton = panel.querySelector(".chart-skeleton");
    var canvas = panel.querySelector("canvas");
    var note = panel.querySelector(".chart-message");
    if (skeleton) skeleton.classList.toggle("hidden", mode !== "loading");
    if (canvas) canvas.classList.toggle("hidden", mode !== "chart");
    if (note) {
      note.classList.toggle("hidden", mode !== "empty" && mode !== "error");
      note.textContent = message || "";
    }
  }

  function failPanel(panel, message) {
    setPanelState(panel, "error", message || "Could not load this chart.");
  }

  function emptyPanel(panel, fallback) {
    panel.style.height = "120px";
    setPanelState(panel, "empty", panel.getAttribute("data-empty") || fallback || "No data available yet.");
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
    return Math.max(220, 36 * Math.max(count, 1) + 48);
  }

  var palette = ["#2563eb", "#f97316", "#0ea5e9", "#6366f1", "#059669", "#e11d48", "#0f172a", "#94a3b8", "#f59e0b", "#14b8a6"];
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
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.tooltip.backgroundColor = "#0f172a";
  Chart.defaults.maintainAspectRatio = false;

  var data;
  try {
    data = JSON.parse(dataNode.textContent);
  } catch (err) {
    showPageError();
    return;
  }

  function doughnut(panel, items, colorMap) {
    items = (items || []).filter(function (item) {
      return Number(item.count) > 0;
    });
    if (!hasCounts(items)) {
      emptyPanel(panel);
      return;
    }
    var canvas = panel.querySelector("canvas");
    setPanelState(panel, "chart");
    var colors = items.map(function (item, index) {
      return (colorMap && colorMap[item.key]) || palette[index % palette.length];
    });
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: labelsOf(items),
        datasets: [{
          data: countsOf(items),
          backgroundColor: colors,
          borderWidth: 0,
          hoverOffset: 4
        }]
      },
      options: {
        cutout: "62%",
        plugins: {
          legend: { position: window.innerWidth < 640 ? "bottom" : "right" }
        }
      }
    });
  }

  function bars(panel, items, color) {
    if (!hasCounts(items)) {
      emptyPanel(panel);
      return;
    }
    var canvas = panel.querySelector("canvas");
    panel.style.height = barHeight(items.length) + "px";
    setPanelState(panel, "chart");
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: labelsOf(items),
        datasets: [{
          data: countsOf(items),
          backgroundColor: color || "#2563eb",
          borderRadius: 8,
          maxBarThickness: 28
        }]
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { color: "rgba(148, 163, 184, 0.18)" }
          },
          y: {
            grid: { display: false }
          }
        }
      }
    });
  }

  function line(panel, trend) {
    if (!trend || !trend.labels || !trend.labels.length) {
      emptyPanel(panel);
      return;
    }
    var canvas = panel.querySelector("canvas");
    setPanelState(panel, "chart");
    new Chart(canvas, {
      type: "line",
      data: {
        labels: trend.labels,
        datasets: [{
          label: "Applications",
          data: trend.counts,
          borderColor: "#2563eb",
          backgroundColor: "rgba(37, 99, 235, 0.12)",
          fill: true,
          tension: 0.35,
          pointRadius: trend.labels.length > 20 ? 0 : 3,
          pointBackgroundColor: "#2563eb"
        }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { color: "rgba(148, 163, 184, 0.18)" }
          },
          x: { grid: { display: false } }
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
  bind("trend", function (panel) {
    line(panel, data.trend);
  });
  bind("skills", function (panel) {
    bars(panel, (data.skills || {}).in_demand || [], "#2563eb");
  });
  bind("companyJobs", function (panel) {
    bars(panel, (data.companies || {}).by_jobs || [], "#0f172a");
  });
  bind("locations", function (panel) {
    bars(panel, (data.jobs || {}).by_location || [], "#0ea5e9");
  });
  bind("resumes", function (panel) {
    doughnut(panel, (data.candidates || {}).resume || [], null);
  });
  bind("education", function (panel) {
    bars(panel, (data.candidates || {}).by_education || [], "#6366f1");
  });
  bind("candidateSkills", function (panel) {
    bars(panel, (data.candidates || {}).skills || [], "#f97316");
  });
  bind("courseSkills", function (panel) {
    bars(panel, (data.courses || {}).by_skill || [], "#059669");
  });
  bind("courseCompanies", function (panel) {
    bars(panel, (data.courses || {}).by_company || [], "#2563eb");
  });
  bind("companyApps", function (panel) {
    bars(panel, (data.companies || {}).by_applications || [], "#e11d48");
  });
})();
