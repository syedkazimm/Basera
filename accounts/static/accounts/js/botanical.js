// Small helpers for the botanical page shell: mobile menu and description tabs.
(function () {
  var toggle = document.querySelector('.bt-menu-toggle');
  var panel = document.getElementById('bt-nav');
  if (toggle && panel) {
    toggle.addEventListener('click', function () {
      var open = panel.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  document.querySelectorAll('[data-tabs]').forEach(function (root) {
    var tabs = Array.prototype.slice.call(root.querySelectorAll('[role="tab"]'));
    function select(tab) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
        root.querySelector('#' + t.getAttribute('aria-controls')).hidden = !on;
      });
    }
    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { select(tab); });
      tab.addEventListener('keydown', function (e) {
        var next = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null;
        if (next === null) return;
        var target = tabs[(next + tabs.length) % tabs.length];
        select(target); target.focus(); e.preventDefault();
      });
    });
  });
})();
// 3. Cart feedback. Cart changes come back as fragments (HTMX) with the message
//    in an HX-Trigger header, so: turn that into a toast that fades on its own,
//    and put keyboard focus back on the control that was just used instead of
//    dropping it to the top of the page.
(function () {
  var TOAST_LIFE = 4000;
  var FADE = 240;

  function dismiss(toast) {
    if (toast.dataset.leaving === "1") return;
    toast.dataset.leaving = "1";
    toast.classList.add("is-leaving");
    window.setTimeout(function () { toast.remove(); }, FADE);
  }

  function toast(text, level) {
    var box = document.getElementById("bt-toasts");
    if (!box || !text) return;
    var node = document.createElement("div");
    node.className = "bt-toast" + (level === "error" ? " bt-toast--error" : "");
    node.setAttribute("role", "status");
    node.textContent = text;
    box.appendChild(node);
    window.setTimeout(function () { dismiss(node); }, TOAST_LIFE);
  }

  function show(event) {
    var detail = event.detail || {};
    toast(detail.message, detail.level);
  }
  document.addEventListener("cart:notice", show);
  document.addEventListener("basera:notice", show);

  var usedControl = null;

  document.addEventListener("htmx:beforeRequest", function (event) {
    var el = event.detail && event.detail.elt;
    if (!el || !el.getAttribute) return;
    // the request element is the form; the control is the button inside it
    var control = el.getAttribute("data-cart-action");
    if (!control && el.querySelector) {
      var inner = el.querySelector("[data-cart-action]");
      control = inner ? inner.getAttribute("data-cart-action") : null;
    }
    usedControl = control;
  });

  document.addEventListener("htmx:afterSettle", function () {
    if (!usedControl) return;
    var twin = document.querySelector('[data-cart-action="' + usedControl + '"]');
    if (twin && !twin.disabled) twin.focus({ preventScroll: true });
    usedControl = null;
  });
})();
// 4. Confirm dialogs. htmx drops a <dialog data-modal> into the page; open it as
//    a modal (focus stays inside, Escape closes it), and tidy up when it closes.
//    If the thing was deleted, its card and button are gone, so focus moves to
//    the list's heading.
(function () {
  var opener = null;

  document.addEventListener("htmx:beforeRequest", function (event) {
    var el = event.detail && event.detail.elt;
    if (el && el.getAttribute && el.getAttribute("hx-target") === "#bt-dialog") opener = el;
  });

  document.addEventListener("htmx:afterSettle", function () {
    var dialog = document.querySelector("dialog[data-modal]:not([open])");
    if (dialog && !dialog.dataset.shown) {
      dialog.dataset.shown = "1";
      dialog.addEventListener("close", function () {
        dialog.remove();
        if (opener && opener.isConnected) opener.focus();
      });
      dialog.showModal();
    } else if (opener && !opener.isConnected && !document.querySelector("dialog[data-modal]")) {
      var heading = document.querySelector("#profiles-body h2");
      if (heading) heading.focus({ preventScroll: true });
      opener = null;
    }
  });
})();
