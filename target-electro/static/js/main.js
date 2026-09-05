document.addEventListener("DOMContentLoaded", function () {
  var panel = document.getElementById("ai-panel");
  var overlay = document.getElementById("ai-overlay");
  var toggleBtn = document.getElementById("ai-toggle");
  var aiOpenButtons = document.querySelectorAll("[data-ai-open]");
  var closeBtn = document.getElementById("ai-close");
  var form = document.getElementById("ai-form");
  var input = document.getElementById("ai-query");
  var messages = document.getElementById("ai-messages");

  function openPanel() {
    panel.classList.add("open");
    overlay.classList.add("open");
  }
  function closePanel() {
    panel.classList.remove("open");
    overlay.classList.remove("open");
  }

  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      panel.classList.contains("open") ? closePanel() : openPanel();
    });
  }
  aiOpenButtons.forEach(function (btn) { btn.addEventListener("click", openPanel); });
  if (closeBtn) closeBtn.addEventListener("click", closePanel);
  if (overlay) overlay.addEventListener("click", closePanel);

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var query = input.value.trim();
      if (!query) return;

      var userBubble = document.createElement("div");
      userBubble.className = "ai-msg";
      userBubble.innerHTML = "<strong>أنت:</strong> " + escapeHtml(query);
      messages.appendChild(userBubble);
      input.value = "";
      messages.scrollTop = messages.scrollHeight;

      fetch("/api/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query })
      })
        .then(function (r) {
          if (!r.ok) throw new Error("AI request failed");
          return r.json();
        })
        .then(function (data) {
          var reply = document.createElement("div");
          reply.className = "ai-msg";
          reply.innerHTML = "<strong>Target AI:</strong> " + escapeHtml(data.message);
          messages.appendChild(reply);

          data.products.forEach(function (p) {
            var card = document.createElement("div");
            card.className = "ai-result-card";
            card.innerHTML =
              '<img src="' + (p.image || "") + '" onerror="this.style.visibility=\'hidden\'">' +
              '<div class="ai-result-info">' +
              '<a href="' + p.url + '">' + escapeHtml(p.name) + "</a><br>" +
              p.price + (p.old_price ? ' <span style="text-decoration:line-through;color:#8a8a8a">' + p.old_price + "</span>" : "") +
              "<br><span>" + p.stock_status + "</span>" +
              "</div>";
            messages.appendChild(card);
          });
          messages.scrollTop = messages.scrollHeight;
        })
        .catch(function () {
          var reply = document.createElement("div");
          reply.className = "ai-msg ai-msg-assistant";
          reply.innerHTML = "<strong>Target AI:</strong> صار خطأ بسيط. جرّب مرة ثانية.";
          messages.appendChild(reply);
          messages.scrollTop = messages.scrollHeight;
        });
    });
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.innerText = str;
    return div.innerHTML;
  }

  // Admin: warn before wiping specs when product type changes on an existing product.
  // (Spec-field re-rendering itself is handled inline in admin/product_form.html —
  // this only guards against silently losing data on an edit.)
  var typeSelect = document.getElementById("product_type_id");
  if (typeSelect && typeSelect.dataset.original) {
    typeSelect.addEventListener("change", function () {
      if (typeSelect.dataset.original && typeSelect.value !== typeSelect.dataset.original) {
        var ok = confirm("تغيير نوع المنتج قد يؤدي إلى إزالة بعض المواصفات غير المتوافقة. هل تريد المتابعة؟");
        if (!ok) {
          typeSelect.value = typeSelect.dataset.original;
          typeSelect.dispatchEvent(new Event("change"));
        }
      }
    }, true); // capture phase: this warning check runs before the field-rebuild listener
  }
});
