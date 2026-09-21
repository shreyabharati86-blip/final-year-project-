document.addEventListener("DOMContentLoaded", function () {
  var navToggle = document.getElementById("nav-toggle");
  var navLinks = document.getElementById("nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var open = navLinks.classList.toggle("hidden") === false;
      navLinks.classList.toggle("flex", open);
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      navToggle.textContent = open ? "Close" : "Menu";
    });
  }

  document.querySelectorAll(".flash-close").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var note = btn.closest("[data-flash]");
      if (note) note.remove();
    });
  });

  setTimeout(function () {
    document.querySelectorAll("[data-flash]").forEach(function (note) {
      note.style.transition = "opacity .3s ease, transform .3s ease";
      note.style.opacity = "0";
      note.style.transform = "translateY(-6px)";
      setTimeout(function () {
        note.remove();
      }, 300);
    });
  }, 6000);

  var roleInputs = document.querySelectorAll('input[name="role"]');
  var companyFields = document.getElementById("company-fields");
  function syncCompanyFields() {
    if (!companyFields) return;
    var selected = document.querySelector('input[name="role"]:checked');
    var isCompany = selected && selected.value === "company";
    companyFields.classList.toggle("hidden", !isCompany);
    companyFields.querySelectorAll("input").forEach(function (input) {
      input.required = isCompany && input.name === "company_name";
    });
  }
  roleInputs.forEach(function (input) {
    input.addEventListener("change", syncCompanyFields);
  });
  syncCompanyFields();

  document.querySelectorAll("[data-password-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.getElementById(btn.getAttribute("data-password-toggle"));
      if (!input) return;
      var hidden = input.type === "password";
      input.type = hidden ? "text" : "password";
      btn.textContent = hidden ? "Hide" : "Show";
    });
  });

  var tabButtons = document.querySelectorAll(".tab-btn");
  var tabPanels = document.querySelectorAll(".tab-panel");
  function activateTab(target) {
    var matched = false;
    tabButtons.forEach(function (item) {
      var selected = item.getAttribute("data-tab") === target;
      item.setAttribute("aria-selected", selected ? "true" : "false");
      if (selected) matched = true;
    });
    if (!matched) return;
    tabPanels.forEach(function (panel) {
      panel.classList.toggle("hidden", panel.id !== "tab-" + target);
    });
  }
  tabButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      activateTab(btn.getAttribute("data-tab"));
    });
  });
  var params = new URLSearchParams(window.location.search);
  var initialTab = params.get("tab") || (window.location.hash || "").replace("#", "");
  if (initialTab) activateTab(initialTab);

  document.querySelectorAll("[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });
});