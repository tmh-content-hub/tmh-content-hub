/* ─────────────────────────────────────────────────────────
   TMH Content Hub — Client-side JS
───────────────────────────────────────────────────────── */

// ─── Dashboard: expand / collapse cards ──────────────────

function toggleCard(destId) {
  const card = document.getElementById("card-" + destId);
  const btn  = card.querySelector(".dest-card-header");
  const isOpen = card.classList.contains("dest-card--open");

  if (isOpen) {
    card.classList.remove("dest-card--open");
    btn.setAttribute("aria-expanded", "false");
  } else {
    card.classList.add("dest-card--open");
    btn.setAttribute("aria-expanded", "true");
  }
}

// ─── Toast helper ────────────────────────────────────────

function showToast(msg, isError = false) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.toggle("toast--error", isError);
  t.classList.add("toast--visible");
  setTimeout(() => t.classList.remove("toast--visible"), 3200);
}

// ─── Modal helpers ───────────────────────────────────────

let _confirmCallback = null;

function showConfirm(msg, callback) {
  document.getElementById("confirm-msg").textContent = msg;
  document.getElementById("confirm-modal").style.display = "flex";
  _confirmCallback = callback;
  document.getElementById("confirm-yes").onclick = () => {
    closeModal();
    callback();
  };
}

function closeModal() {
  document.getElementById("confirm-modal").style.display = "none";
  _confirmCallback = null;
}

let _pwCustId = null;

function resetPassword(custId, custName) {
  _pwCustId = custId;
  document.getElementById("pw-modal-name").textContent = custName;
  document.getElementById("pw-new-value").value = "";
  document.getElementById("pw-modal").style.display = "flex";
  setTimeout(() => document.getElementById("pw-new-value").focus(), 50);
}

function closePwModal() {
  document.getElementById("pw-modal").style.display = "none";
  _pwCustId = null;
}

async function submitResetPassword() {
  const pw = document.getElementById("pw-new-value").value.trim();
  if (!pw) { showToast("Please enter a new password.", true); return; }
  try {
    const res = await fetch(`/admin/api/customers/${_pwCustId}/password`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw })
    });
    const json = await res.json();
    if (json.success) {
      closePwModal();
      showToast("Password updated successfully.");
    } else {
      showToast(json.error || "Failed to update password.", true);
    }
  } catch(e) {
    showToast("Network error.", true);
  }
}

// ─── Admin: Customers tab ─────────────────────────────────

async function addCustomer(e) {
  e.preventDefault();
  const name     = document.getElementById("new-cust-name").value.trim();
  const email    = document.getElementById("new-cust-email").value.trim();
  const password = document.getElementById("new-cust-password").value.trim();

  if (!name || !email || !password) {
    showToast("Please fill in all fields.", true);
    return;
  }

  try {
    const res = await fetch("/admin/api/customers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password })
    });
    const json = await res.json();
    if (json.success) {
      showToast(`Customer "${name}" added.`);
      // Add row to table
      const tbody = document.getElementById("customers-tbody");
      // Remove "no customers" placeholder if present
      const empty = tbody.querySelector(".empty-cell");
      if (empty) empty.closest("tr").remove();

      const row = document.createElement("tr");
      row.id = `cust-row-${json.customer.id}`;
      row.setAttribute("data-cust-id", json.customer.id);
      row.innerHTML = `
        <td>${escHtml(json.customer.name)}</td>
        <td>${escHtml(json.customer.email)}</td>
        <td><span class="dest-count">0 destinations</span></td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-outline" onclick="resetPassword('${json.customer.id}', '${escHtml(json.customer.name)}')">Reset password</button>
          <button class="btn btn-sm btn-danger" onclick="deleteCustomer('${json.customer.id}', '${escHtml(json.customer.name)}')">Delete</button>
        </td>`;
      tbody.appendChild(row);

      // Also update TMH_DATA so Assign tab stays fresh
      TMH_DATA.customers.push({
        id: json.customer.id,
        name: json.customer.name,
        email: json.customer.email,
        destinations: []
      });
      refreshAssignSelect();

      // Clear form
      document.getElementById("new-cust-name").value = "";
      document.getElementById("new-cust-email").value = "";
      document.getElementById("new-cust-password").value = "";
    } else {
      showToast(json.error || "Failed to add customer.", true);
    }
  } catch(e) {
    showToast("Network error.", true);
  }
}

async function deleteCustomer(custId, custName) {
  showConfirm(`Delete customer "${custName}"? This cannot be undone.`, async () => {
    try {
      const res = await fetch(`/admin/api/customers/${custId}`, { method: "DELETE" });
      const json = await res.json();
      if (json.success) {
        document.getElementById(`cust-row-${custId}`)?.remove();
        TMH_DATA.customers = TMH_DATA.customers.filter(c => c.id !== custId);
        refreshAssignSelect();
        showToast(`Customer "${custName}" deleted.`);
      }
    } catch(e) {
      showToast("Network error.", true);
    }
  });
}

// ─── Admin: Destinations tab ──────────────────────────────

async function addDestination(e) {
  e.preventDefault();
  const name   = document.getElementById("new-dest-name").value.trim();
  const flag   = document.getElementById("new-dest-flag").value.trim() || "🌍";
  const status = document.getElementById("new-dest-status").value;

  if (!name) { showToast("Please enter a destination name.", true); return; }

  try {
    const res = await fetch("/admin/api/destinations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, flag, status })
    });
    const json = await res.json();
    if (json.success) {
      showToast(`Destination "${name}" added.`);
      const tbody = document.getElementById("destinations-tbody");
      const empty = tbody.querySelector(".empty-cell");
      if (empty) empty.closest("tr").remove();

      const row = document.createElement("tr");
      row.id = `dest-row-${json.destination.id}`;
      row.setAttribute("data-dest-id", json.destination.id);
      row.innerHTML = `
        <td>${escHtml(json.destination.flag)}</td>
        <td>${escHtml(json.destination.name)}</td>
        <td><code class="id-code">${escHtml(json.destination.id)}</code></td>
        <td>
          <select class="status-select" onchange="updateStatus('${json.destination.id}', this.value)">
            <option value="ready" ${status==='ready'?'selected':''}>Ready</option>
            <option value="coming_soon" ${status==='coming_soon'?'selected':''}>Coming Soon</option>
          </select>
        </td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-danger" onclick="deleteDestination('${json.destination.id}', '${escHtml(json.destination.name)}')">Delete</button>
        </td>`;
      tbody.appendChild(row);

      TMH_DATA.destinations.push({
        id: json.destination.id,
        name: json.destination.name,
        flag: json.destination.flag,
        status: status,
        files: { blog_docx:"", social_posts:"", promo_assets:"", guide_pdf:"", images_folder:"", canva_guide:"", canva_carousel:"", canva_pinterest:"" }
      });

      document.getElementById("new-dest-name").value = "";
      document.getElementById("new-dest-flag").value = "";
    } else {
      showToast(json.error || "Failed to add destination.", true);
    }
  } catch(e) {
    showToast("Network error.", true);
  }
}

async function deleteDestination(destId, destName) {
  showConfirm(`Delete destination "${destName}"? It will be removed from all customers.`, async () => {
    try {
      const res = await fetch(`/admin/api/destinations/${destId}`, { method: "DELETE" });
      const json = await res.json();
      if (json.success) {
        document.getElementById(`dest-row-${destId}`)?.remove();
        TMH_DATA.destinations = TMH_DATA.destinations.filter(d => d.id !== destId);
        // Remove from all customers in local data
        TMH_DATA.customers.forEach(c => {
          c.destinations = c.destinations.filter(d => d !== destId);
        });
        showToast(`Destination "${destName}" deleted.`);
      }
    } catch(e) {
      showToast("Network error.", true);
    }
  });
}

async function updateStatus(destId, newStatus) {
  try {
    const res = await fetch(`/admin/api/destinations/${destId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    const json = await res.json();
    if (json.success) showToast("Status updated.");
    else showToast(json.error || "Failed to update status.", true);
  } catch(e) {
    showToast("Network error.", true);
  }
}

// ─── Admin: Assign tab ────────────────────────────────────

function refreshAssignSelect() {
  const sel = document.getElementById("assign-customer-picker");
  if (!sel) return;
  const currentVal = sel.value;
  sel.innerHTML = '<option value="">— Select a customer —</option>';
  TMH_DATA.customers.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.name} (${c.email})`;
    if (c.id === currentVal) opt.selected = true;
    sel.appendChild(opt);
  });
  if (!currentVal) {
    document.getElementById("assign-panel-content").style.display = "none";
  }
}

function loadAssignPanel(custId) {
  const container = document.getElementById("assign-panel-content");
  if (!custId) { container.style.display = "none"; return; }

  const customer = TMH_DATA.customers.find(c => c.id === custId);
  if (!customer) { container.style.display = "none"; return; }

  container.style.display = "block";
  container.innerHTML = "";

  if (TMH_DATA.destinations.length === 0) {
    container.innerHTML = '<p class="panel-hint" style="padding:1rem;">No destinations created yet. Add destinations in the Destinations tab first.</p>';
    return;
  }

  TMH_DATA.destinations.forEach(dest => {
    const isAssigned = customer.destinations.includes(dest.id);
    const files = dest.files || {};

    const block = document.createElement("div");
    block.className = "assign-dest-row";
    block.id = `assign-${custId}-${dest.id}`;

    block.innerHTML = `
      <div class="assign-dest-header">
        <label class="assign-checkbox-label">
          <input type="checkbox" id="chk-${custId}-${dest.id}"
            ${isAssigned ? "checked" : ""}
            onchange="toggleAssign('${custId}', '${dest.id}', this.checked, '${escHtml(dest.name)}')" />
          <span>${escHtml(dest.flag)} ${escHtml(dest.name)}</span>
        </label>
      </div>
      <div class="assign-links-grid" id="links-${custId}-${dest.id}">
        ${linkField("Blog DOCX URL", `f-blog_docx-${custId}-${dest.id}`, files.blog_docx || "")}
        ${linkField("Social Posts URL", `f-social_posts-${custId}-${dest.id}`, files.social_posts || "")}
        ${linkField("Promo Assets URL", `f-promo_assets-${custId}-${dest.id}`, files.promo_assets || "")}
        ${linkField("Guide PDF URL", `f-guide_pdf-${custId}-${dest.id}`, files.guide_pdf || "")}
        ${linkField("Images Folder URL", `f-images_folder-${custId}-${dest.id}`, files.images_folder || "")}
        ${linkField("Canva — Destination Guide", `f-canva_guide-${custId}-${dest.id}`, files.canva_guide || "")}
        ${linkField("Canva — Instagram Carousel", `f-canva_carousel-${custId}-${dest.id}`, files.canva_carousel || "")}
        ${linkField("Canva — Pinterest Pins", `f-canva_pinterest-${custId}-${dest.id}`, files.canva_pinterest || "")}
      </div>
      <div class="assign-save-btn">
        <button class="btn btn-primary btn-sm" onclick="saveLinks('${custId}', '${dest.id}', '${escHtml(dest.name)}')">Save Links for ${escHtml(dest.name)}</button>
      </div>`;

    container.appendChild(block);
  });
}

function linkField(label, id, value) {
  return `
    <div class="form-group">
      <label>${escHtml(label)}</label>
      <input type="url" id="${id}" value="${escHtml(value)}" placeholder="https://" />
    </div>`;
}

async function toggleAssign(custId, destId, assigned, destName) {
  try {
    const res = await fetch("/admin/api/assign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_id: custId, destination_id: destId, assigned })
    });
    const json = await res.json();
    if (json.success) {
      // Update local data
      const cust = TMH_DATA.customers.find(c => c.id === custId);
      if (cust) {
        if (assigned && !cust.destinations.includes(destId)) cust.destinations.push(destId);
        else if (!assigned) cust.destinations = cust.destinations.filter(d => d !== destId);
      }
      showToast(assigned ? `${destName} assigned.` : `${destName} unassigned.`);
    } else {
      showToast(json.error || "Failed to update assignment.", true);
    }
  } catch(e) {
    showToast("Network error.", true);
  }
}

async function saveLinks(custId, destId, destName) {
  const fields = ["blog_docx", "social_posts", "promo_assets", "guide_pdf", "images_folder", "canva_guide", "canva_carousel", "canva_pinterest"];
  const body = {};
  fields.forEach(f => {
    const el = document.getElementById(`f-${f}-${custId}-${destId}`);
    if (el) body[f] = el.value.trim();
  });

  try {
    const res = await fetch(`/admin/api/destinations/${destId}/files`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const json = await res.json();
    if (json.success) {
      // Update local data
      const dest = TMH_DATA.destinations.find(d => d.id === destId);
      if (dest) Object.assign(dest.files, body);
      showToast(`Links saved for ${destName}.`);
    } else {
      showToast(json.error || "Failed to save links.", true);
    }
  } catch(e) {
    showToast("Network error.", true);
  }
}

// ─── Tab switching ────────────────────────────────────────

function switchTab(name) {
  ["customers", "destinations", "assign", "settings"].forEach(tab => {
    document.getElementById(`tab-${tab}`)?.classList.toggle("tab-btn--active", tab === name);
    document.getElementById(`panel-${tab}`)?.classList.toggle("tab-panel--active", tab === name);
  });
}

async function changeAdminPassword(e) {
  e.preventDefault();
  const current = document.getElementById("admin-pw-current").value;
  const newPw   = document.getElementById("admin-pw-new").value;
  const confirm = document.getElementById("admin-pw-confirm").value;

  if (newPw !== confirm) {
    showToast("New passwords don't match.", true);
    return;
  }
  if (newPw.length < 6) {
    showToast("New password must be at least 6 characters.", true);
    return;
  }

  try {
    const res = await fetch("/admin/api/admin-password", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: current, new_password: newPw })
    });
    const json = await res.json();
    if (json.success) {
      showToast("Admin password updated successfully!");
      document.getElementById("admin-pw-current").value = "";
      document.getElementById("admin-pw-new").value = "";
      document.getElementById("admin-pw-confirm").value = "";
    } else {
      showToast(json.error || "Failed to update password.", true);
    }
  } catch(e) {
    showToast("Network error.", true);
  }
}

// ─── Utility ─────────────────────────────────────────────

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
