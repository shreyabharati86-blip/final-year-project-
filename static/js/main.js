document.addEventListener("DOMContentLoaded", function () {
  var role = document.getElementById("role");
  var companyFields = document.getElementById("company-fields");
  if (role && companyFields) {
    function toggleCompany() {
      companyFields.classList.toggle("d-none", role.value !== "company");
    }
    role.addEventListener("change", toggleCompany);
    toggleCompany();
  }
});
