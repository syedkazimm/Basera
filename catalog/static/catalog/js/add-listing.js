// Add a plant page (US-13): live listing preview and a quick photo check.
// The server checks everything again; this only gives earlier feedback.
(function () {
  var form = document.getElementById("listing-form");
  if (!form) return;

  var maxBytes = Number(form.dataset.maxImageBytes) || 2 * 1024 * 1024;
  var outputs = {};
  document.querySelectorAll("[data-preview-out]").forEach(function (el) {
    outputs[el.dataset.previewOut] = el;
  });

  // 1. Name, scientific name, price and stock update the preview card.
  function stockText(value) {
    if (value === "") return "Add stock";
    var n = Number(value);
    if (!Number.isInteger(n) || n < 0) return "Add stock";
    return n === 0 ? "Out of stock" : "In stock · " + n + " available";
  }

  function update(input) {
    var key = input.dataset.preview;
    var out = outputs[key];
    if (!out) return;
    var value = input.value.trim();
    out.textContent = key === "stock" ? stockText(value) : (value || out.dataset.empty);
  }

  form.querySelectorAll("[data-preview]").forEach(function (input) {
    input.addEventListener("input", function () { update(input); });
    update(input);
  });

  // 2. Photo: show the chosen file, check type and size, preview the image.
  var fileInput = document.getElementById("id_image");
  var drop = form.querySelector("[data-drop]");
  var title = form.querySelector("[data-drop-title]");
  var hint = form.querySelector("[data-drop-hint]");
  var error = form.querySelector("[data-drop-error]");
  var media = document.querySelector("[data-preview-media]");
  var placeholder = media ? media.innerHTML : "";
  var objectUrl = null;

  function sizeText(bytes) {
    return bytes >= 1024 * 1024 ? (bytes / 1024 / 1024).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function showPlaceholder() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    media.innerHTML = placeholder;
  }

  fileInput.addEventListener("change", function () {
    var file = fileInput.files[0];
    if (!file) {
      showPlaceholder();
      return;
    }
    var okType = /\.(jpe?g|png)$/i.test(file.name) && /^image\/(jpeg|png)$/.test(file.type);
    var okSize = file.size < maxBytes;
    if (!okType || !okSize) {
      fileInput.value = "";
      drop.classList.add("is-invalid");
      fileInput.setAttribute("aria-invalid", "true");
      title.textContent = "Choose a different file";
      hint.textContent = file.name + ", " + sizeText(file.size) + " was not added";
      error.hidden = false;
      showPlaceholder();
      return;
    }
    drop.classList.remove("is-invalid");
    fileInput.removeAttribute("aria-invalid");
    error.hidden = true;
    title.textContent = file.name;
    hint.textContent = sizeText(file.size) + " · choose a different file to replace it";
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    var img = document.createElement("img");
    img.src = objectUrl;
    img.alt = "Photo preview";
    media.replaceChildren(img);
  });

  ["dragenter", "dragover"].forEach(function (type) {
    drop.addEventListener(type, function () { drop.classList.add("is-dragging"); });
  });
  ["dragleave", "drop"].forEach(function (type) {
    drop.addEventListener(type, function () { drop.classList.remove("is-dragging"); });
  });
})();
