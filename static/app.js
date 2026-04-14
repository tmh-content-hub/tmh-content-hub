/* ─────────────────────────────────────────────────────────
   TMH Content Hub — Client JS
───────────────────────────────────────────────────────── */

// ─── Dashboard: expand / collapse cards ──────────────────

function toggleCard(destId) {
  const card = document.getElementById("card-" + destId);
  if (!card) return;
  const isOpen = card.classList.contains("dest-card--open");
  card.classList.toggle("dest-card--open", !isOpen);
  card.querySelector(".dest-card-header")?.setAttribute("aria-expanded", String(!isOpen));
}

// ─── Dashboard: change password ──────────────────────────

async function changeMyPassword(e) {
  e.preventDefault();
  const current = document.getElementById("cpw-current").value;
  const newPw   = document.getElementById("cpw-new").value;
  const confirm = document.getElementById("cpw-confirm").value;

  if (newPw !== confirm) { showCpwMsg("New passwords don't match.", true); return; }
  if (newPw.length < 6)  { showCpwMsg("Password must be at least 6 characters.", true); return; }

  try {
    const res  = await fetch("/api/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: current, new_password: newPw })
    });
    const json = await res.json();
    if (json.success) {
      showCpwMsg("✅ Password updated successfully!", false);
      document.getElementById("cpw-current").value = "";
      document.getElementById("cpw-new").value = "";
      document.getElementById("cpw-confirm").value = "";
    } else {
      showCpwMsg(json.error || "Failed to update password.", true);
    }
  } catch(e) {
    showCpwMsg("Network error. Please try again.", true);
  }
}

function showCpwMsg(text, isError) {
  const el = document.getElementById("cpw-msg");
  if (!el) return;
  el.textContent = text;
  el.style.display = "block";
  el.className = "cpw-msg " + (isError ? "cpw-msg--error" : "cpw-msg--success");
}

// ─── Toast ────────────────────────────────────────────────

function showToast(msg, isError = false) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.toggle("toast--error", isError);
  t.classList.add("toast--visible");
  setTimeout(() => t.classList.remove("toast--visible"), 3200);
}

// ─── Confirm modal ────────────────────────────────────────

function showConfirm(msg, callback) {
  document.getElementById("confirm-msg").textContent = msg;
  document.getElementById("confirm-modal").style.display = "flex";
  document.getElementById("confirm-yes").onclick = () => { closeModal(); callback(); };
}

function closeModal() {
  document.getElementById("confirm-modal").style.display = "none";
}

// ─── Reset password modal ─────────────────────────────────

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
    const res  = await fetch(`/admin/api/customers/${_pwCustId}/password`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw })
    });
    const json = await res.json();
    if (json.success) { closePwModal(); showToast("Password updated."); }
    else showToast(json.error || "Failed.", true);
  } catch(e) { showToast("Network error.", true); }
}

// ─── Customer detail modal ────────────────────────────────

function openCustomerDetail(custId) {
  const cust = TMH_DATA.customers.find(c => c.id === custId);
  if (!cust) return;
  document.getElementById("cust-detail-id").value               = custId;
  document.getElementById("cust-detail-title").textContent       = cust.name;
  document.getElementById("cust-detail-email").textContent       = cust.email;
  document.getElementById("cust-detail-joined").textContent      = cust.joined_date || "—";
  document.getElementById("cust-detail-last-login").textContent  = fmtLastLogin(cust.last_login);
  document.getElementById("cust-detail-notes").value             = cust.notes || "";
  document.getElementById("cust-detail-plan").value              = cust.plan || "core";
  renderAssignedList(cust);

  // Pro/Managed-only sections
  const plan = cust.plan || "core";
  const isPro = plan === "pro" || plan === "managed";

  // Supplier reels folder
  const reelsFolderSection = document.getElementById("cust-detail-reels-folder-section");
  const reelsUrlInput = document.getElementById("cust-detail-supplier-reels-url");
  if (reelsFolderSection) {
    reelsFolderSection.style.display = isPro ? "" : "none";
    if (reelsUrlInput) reelsUrlInput.value = cust.supplier_reels_url || "";
  }

  const offersSection = document.getElementById("cust-detail-offers-section");
  if (offersSection) {
    if (plan === "pro" || plan === "managed") {
      offersSection.style.display = "";
      const limit = plan === "pro" ? 4 : 8;
      // Count this month's offers for this customer
      const now = new Date();
      const thisMonth = now.getMonth() + 1;
      const thisYear  = now.getFullYear();
      const allCards  = document.querySelectorAll("#offers-cards .admin-offer-card");
      let count = 0;
      allCards.forEach(card => {
        if (card.dataset.customerId === custId) {
          const [cy, cm] = (card.dataset.monthKey || "").split("-").map(Number);
          if (cy === thisYear && cm === thisMonth) count++;
        }
      });
      document.getElementById("cust-detail-offers-count").textContent =
        `${count} of ${limit} reels submitted this month`;
    } else {
      offersSection.style.display = "none";
    }
  }

  document.getElementById("customer-detail-modal").style.display = "flex";
}

function closeCustomerDetail() {
  document.getElementById("customer-detail-modal").style.display = "none";
}

function renderAssignedList(cust) {
  const container = document.getElementById("cust-assigned-list");
  const ids = cust.assigned_dest_ids || [];
  if (ids.length === 0) {
    container.innerHTML = '<span style="color:#888;font-size:.85rem;">No custom assignments — customer sees rolling window.</span>';
    return;
  }
  container.innerHTML = ids.map(id => {
    const d = TMH_DATA.all_destinations.find(x => x.id === id);
    if (!d) return "";
    const label = `${TMH_MONTH_NAMES[d.month-1]} ${d.year}: ${d.name}`;
    return `<span class="assign-tag">${escHtml(label)}
      <button class="assign-tag-remove" onclick="unassignDest('${id}')" title="Remove">×</button>
    </span>`;
  }).join("");
}

async function assignDest() {
  const custId  = document.getElementById("cust-detail-id").value;
  const sel     = document.getElementById("cust-assign-select");
  const dest_id = sel.value;
  if (!dest_id) { showToast("Please select a destination first.", true); return; }
  try {
    const res  = await fetch(`/admin/api/customers/${custId}/assign`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dest_id })
    });
    const json = await res.json();
    if (json.success) {
      const cust = TMH_DATA.customers.find(c => c.id === custId);
      if (cust) cust.assigned_dest_ids = json.assigned_dest_ids;
      renderAssignedList(cust);
      updateCustomerBadge(custId, json.assigned_dest_ids);
      sel.value = "";
      showToast("Destination assigned.");
    } else showToast(json.error || "Failed.", true);
  } catch(e) { showToast("Network error.", true); }
}

async function unassignDest(destId) {
  const custId = document.getElementById("cust-detail-id").value;
  try {
    const res  = await fetch(`/admin/api/customers/${custId}/unassign`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dest_id: destId })
    });
    const json = await res.json();
    if (json.success) {
      const cust = TMH_DATA.customers.find(c => c.id === custId);
      if (cust) cust.assigned_dest_ids = json.assigned_dest_ids;
      renderAssignedList(cust);
      updateCustomerBadge(custId, json.assigned_dest_ids);
      showToast("Assignment removed.");
    } else showToast(json.error || "Failed.", true);
  } catch(e) { showToast("Network error.", true); }
}

async function clearAllAssignments() {
  const custId = document.getElementById("cust-detail-id").value;
  const cust   = TMH_DATA.customers.find(c => c.id === custId);
  if (!cust || !cust.assigned_dest_ids || cust.assigned_dest_ids.length === 0) {
    showToast("No assignments to clear.", true); return;
  }
  showConfirm("Clear all assigned destinations for this customer? They will revert to the rolling window.", async () => {
    try {
      const res  = await fetch(`/admin/api/customers/${custId}/clear-assignments`, {
        method: "PUT", headers: { "Content-Type": "application/json" }
      });
      let json;
      try { json = await res.json(); } catch(_) { json = {}; }
      if (res.status === 401) {
        showToast("Session expired — please refresh the page and log in again.", true); return;
      }
      if (!json.success) {
        showToast(json.error || "Failed to clear assignments.", true); return;
      }
      cust.assigned_dest_ids = [];
      renderAssignedList(cust);
      updateCustomerBadge(custId, []);
      showToast("All assignments cleared — customer is back on rolling window.");
    } catch(e) {
      showToast("Network error — assignments not cleared.", true);
    }
  });
}

function updateCustomerBadge(custId, ids) {
  const row = document.getElementById(`cust-row-${custId}`);
  if (!row) return;
  const cell = row.querySelectorAll("td")[5]; // Name, Email, Joined, Plan, LastLogin, Destinations
  if (!cell) return;
  cell.innerHTML = ids.length > 0
    ? `<span class="badge badge--assigned">${ids.length} assigned</span>`
    : `<span style="color:#888;font-size:.85rem;">Rolling window</span>`;
}

async function saveCustomerDetail() {
  const custId           = document.getElementById("cust-detail-id").value;
  const notes            = document.getElementById("cust-detail-notes").value;
  const plan             = document.getElementById("cust-detail-plan").value;
  const supplierReelsUrl = (document.getElementById("cust-detail-supplier-reels-url")?.value || "").trim();
  const isPro = plan === "pro" || plan === "managed";
  try {
    const adminFetch = (url, body) => {
      const ctrl = new AbortController();
      setTimeout(() => ctrl.abort(), 15000);
      return fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body), signal: ctrl.signal });
    };
    const fetches = [
      adminFetch(`/admin/api/customers/${custId}/notes`, { notes }),
      adminFetch(`/admin/api/customers/${custId}/plan`, { plan })
    ];
    if (isPro) {
      fetches.push(adminFetch(`/admin/api/customers/${custId}/supplier-reels`, { supplier_reels_url: supplierReelsUrl }));
    }
    const responses = await Promise.all(fetches);
    if (responses.some(r => r.status === 401)) { window.location.href = "/admin/login?reason=expired"; return; }
    const jsons  = await Promise.all(responses.map(r => r.json()));
    const failed = jsons.find(j => !j.success);
    if (!failed) {
      const cust = TMH_DATA.customers.find(c => c.id === custId);
      if (cust) { cust.notes = notes; cust.plan = plan; if (isPro) cust.supplier_reels_url = supplierReelsUrl; }
      updatePlanBadge(custId, plan);
      closeCustomerDetail();
      showToast("Customer details saved.");
    } else { showToast(failed.error || "Failed.", true); }
  } catch(e) {
    if (e.name === "AbortError") { showToast("Save timed out — please refresh and try again.", true); }
    else { showToast("Network error.", true); }
  }
}

function updatePlanBadge(custId, plan) {
  const row = document.getElementById(`cust-row-${custId}`);
  if (!row) return;
  const cell = row.querySelectorAll("td")[3];
  if (!cell) return;
  const label = plan.charAt(0).toUpperCase() + plan.slice(1);
  cell.innerHTML = `<span class="badge badge--plan badge--plan-${plan}">${label}</span>`;
}

// ─── Admin: Customers ─────────────────────────────────────

async function addCustomer(e) {
  e.preventDefault();
  const name     = document.getElementById("new-cust-name").value.trim();
  const email    = document.getElementById("new-cust-email").value.trim();
  const password = document.getElementById("new-cust-password").value.trim();

  if (!name || !email || !password) { showToast("Please fill in all fields.", true); return; }

  try {
    const res  = await fetch("/admin/api/customers", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password })
    });
    const json = await res.json();
    if (json.success) {
      showToast(`Customer "${name}" added.`);
      const tbody = document.getElementById("customers-tbody");
      const empty = tbody.querySelector(".empty-cell");
      if (empty) empty.closest("tr").remove();

      const row = document.createElement("tr");
      row.id = `cust-row-${json.customer.id}`;
      row.setAttribute("data-cust-id", json.customer.id);
      row.innerHTML = `
        <td><button class="link-btn" onclick="openCustomerDetail('${json.customer.id}')">${escHtml(json.customer.name)}</button></td>
        <td>${escHtml(json.customer.email)}</td>
        <td>${escHtml(json.customer.joined_date)}</td>
        <td><span class="badge badge--plan badge--plan-core">Core</span></td>
        <td class="last-login-cell"><span style="color:#bbb;">Never</span></td>
        <td><span style="color:#888;font-size:.85rem;">Rolling window</span></td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-outline" onclick="resetPassword('${json.customer.id}', '${escHtml(json.customer.name)}')">Reset pw</button>
          <button class="btn btn-sm btn-danger" onclick="deleteCustomer('${json.customer.id}', '${escHtml(json.customer.name)}')">Delete</button>
        </td>`;
      tbody.appendChild(row);

      TMH_DATA.customers.push({
        id: json.customer.id, name, email, plan: "core",
        joined_date: json.customer.joined_date, last_login: null, notes: "", assigned_dest_ids: []
      });

      document.getElementById("new-cust-name").value  = "";
      document.getElementById("new-cust-email").value = "";
      document.getElementById("new-cust-password").value = "Welcome2TMH!";
    } else { showToast(json.error || "Failed.", true); }
  } catch(e) { showToast("Network error.", true); }
}

async function deleteCustomer(custId, custName) {
  showConfirm(`Delete customer "${custName}"? This cannot be undone.`, async () => {
    try {
      const res  = await fetch(`/admin/api/customers/${custId}`, { method: "DELETE" });
      const json = await res.json();
      if (json.success) {
        document.getElementById(`cust-row-${custId}`)?.remove();
        TMH_DATA.customers = TMH_DATA.customers.filter(c => c.id !== custId);
        showToast(`"${custName}" deleted.`);
      }
    } catch(e) { showToast("Network error.", true); }
  });
}

// ─── Admin: Destinations ──────────────────────────────────

async function addDestination(e) {
  e.preventDefault();
  const name   = document.getElementById("new-dest-name").value.trim();
  const flag   = document.getElementById("new-dest-flag").value.trim() || "🌍";
  const month  = parseInt(document.getElementById("new-dest-month").value);
  const year   = parseInt(document.getElementById("new-dest-year").value);
  const status = document.getElementById("new-dest-status").value;

  if (!name) { showToast("Please enter a destination name.", true); return; }

  try {
    const res  = await fetch("/admin/api/destinations", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, flag, month, year, status })
    });
    const json = await res.json();
    if (json.success) {
      showToast(`${TMH_MONTH_NAMES[month-1]} ${year} — "${name}" added.`);
      const tbody = document.getElementById("destinations-tbody");
      const empty = tbody.querySelector(".empty-cell");
      if (empty) empty.closest("tr").remove();

      const row = document.createElement("tr");
      row.id = `dest-row-${json.destination.id}`;
      row.setAttribute("data-dest-id", json.destination.id);
      row.setAttribute("data-year", year);
      row.setAttribute("data-month", month);
      row.innerHTML = `
        <td>${escHtml(flag)}</td>
        <td><strong>${TMH_MONTH_NAMES[month-1]} ${year}</strong></td>
        <td>${escHtml(name)}</td>
        <td>
          <select class="status-select" onchange="updateStatus('${json.destination.id}', this.value)">
            <option value="ready" ${status==='ready'?'selected':''}>Ready</option>
            <option value="coming_soon" ${status==='coming_soon'?'selected':''}>Coming Soon</option>
          </select>
        </td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-outline" onclick="openEditLinks('${json.destination.id}')">Edit Links</button>
          <button class="btn btn-sm btn-archive" onclick="archiveDestination('${json.destination.id}', '${escHtml(name)}')">Archive</button>
          <button class="btn btn-sm btn-danger" onclick="deleteDestination('${json.destination.id}', '${escHtml(name)}')">Delete</button>
        </td>`;
      tbody.appendChild(row);
      sortDestinationsTable();

      const newDest = {
        id: json.destination.id, name, flag, month, year, status,
        files: { blog_docx:"", social_posts:"", promo_assets:"", guide_pdf:"",
                 images_folder:"", canva_guide:"", canva_carousel:"", canva_pinterest:"" }
      };
      TMH_DATA.destinations.push(newDest);
      TMH_DATA.all_destinations.push(newDest);

      document.getElementById("new-dest-name").value = "";
      document.getElementById("new-dest-flag").value = "";
    } else { showToast(json.error || "Failed.", true); }
  } catch(e) { showToast("Network error.", true); }
}

async function deleteDestination(destId, destName) {
  showConfirm(`Delete "${destName}"? This cannot be undone.`, async () => {
    try {
      const res  = await fetch(`/admin/api/destinations/${destId}`, { method: "DELETE" });
      const json = await res.json();
      if (json.success) {
        document.getElementById(`dest-row-${destId}`)?.remove();
        TMH_DATA.destinations        = TMH_DATA.destinations.filter(d => d.id !== destId);
        TMH_DATA.all_destinations    = TMH_DATA.all_destinations.filter(d => d.id !== destId);
        TMH_DATA.archived_destinations = (TMH_DATA.archived_destinations||[]).filter(d => d.id !== destId);
        showToast(`"${destName}" deleted.`);
      }
    } catch(e) { showToast("Network error.", true); }
  });
}

async function updateStatus(destId, newStatus) {
  try {
    const res  = await fetch(`/admin/api/destinations/${destId}/status`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    const json = await res.json();
    if (json.success) showToast("Status updated.");
    else showToast(json.error || "Failed.", true);
  } catch(e) { showToast("Network error.", true); }
}

// ─── Archive / Reinstate ──────────────────────────────────

async function archiveDestination(destId, destName) {
  showConfirm(`Archive "${destName}"? It will be hidden from customers but kept in your library.`, async () => {
    try {
      const res  = await fetch(`/admin/api/destinations/${destId}/archive`, {
        method: "PUT", headers: { "Content-Type": "application/json" }
      });
      const json = await res.json();
      if (json.success) {
        // Move row from active to archived table
        const row = document.getElementById(`dest-row-${destId}`);
        if (row) {
          row.remove();
          const archivedTbody = document.getElementById("archived-tbody");
          const emptyRow = archivedTbody.querySelector(".empty-cell");
          if (emptyRow) emptyRow.closest("tr").remove();

          const dest = TMH_DATA.destinations.find(d => d.id === destId) ||
                       TMH_DATA.all_destinations.find(d => d.id === destId);
          const monthLabel = dest ? TMH_MONTH_NAMES[dest.month-1] + " " + dest.year : "—";

          const newRow = document.createElement("tr");
          newRow.id = `dest-row-${destId}`;
          newRow.className = "row-archived";
          newRow.innerHTML = `
            <td>${dest ? escHtml(dest.flag) : "🌍"}</td>
            <td style="color:#888;">${monthLabel}</td>
            <td style="color:#888;">${escHtml(destName)}</td>
            <td class="actions-cell">
              <button class="btn btn-sm btn-reinstate" onclick="openReinstateModal('${destId}', '${escHtml(destName)}')">Reinstate</button>
              <button class="btn btn-sm btn-danger" onclick="deleteDestination('${destId}', '${escHtml(destName)}')">Delete</button>
            </td>`;
          archivedTbody.appendChild(newRow);
        }
        TMH_DATA.destinations = TMH_DATA.destinations.filter(d => d.id !== destId);
        const d = TMH_DATA.all_destinations.find(x => x.id === destId);
        if (d) {
          d.status = 'archived';
          TMH_DATA.archived_destinations = TMH_DATA.archived_destinations || [];
          TMH_DATA.archived_destinations.push(d);
        }
        showToast(`"${destName}" archived.`);
      } else showToast(json.error || "Failed.", true);
    } catch(e) { showToast("Network error.", true); }
  });
}

let _reinstateDestId = null;

function openReinstateModal(destId, destName) {
  _reinstateDestId = destId;
  document.getElementById("reinstate-dest-id").value          = destId;
  document.getElementById("reinstate-dest-name").textContent  = destName;
  document.getElementById("reinstate-modal").style.display    = "flex";
}

function closeReinstateModal() {
  document.getElementById("reinstate-modal").style.display = "none";
  _reinstateDestId = null;
}

async function submitReinstate() {
  const destId = document.getElementById("reinstate-dest-id").value;
  const month  = parseInt(document.getElementById("reinstate-month").value);
  const year   = parseInt(document.getElementById("reinstate-year").value);
  const btn    = document.querySelector("#reinstate-modal .btn-primary");
  if (btn) { btn.disabled = true; btn.textContent = "Reinstating…"; }

  try {
    const res  = await fetch(`/admin/api/destinations/${destId}/reinstate`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month, year })
    });
    const json = await res.json();
    if (json.success) {
      const d = json.destination;
      // Remove from archived table
      document.getElementById(`dest-row-${destId}`)?.remove();

      // Add to active table
      const tbody = document.getElementById("destinations-tbody");
      const emptyRow = tbody.querySelector(".empty-cell");
      if (emptyRow) emptyRow.closest("tr").remove();

      const row = document.createElement("tr");
      row.id = `dest-row-${destId}`;
      row.setAttribute("data-dest-id", destId);
      row.setAttribute("data-year", d.year);
      row.setAttribute("data-month", d.month);
      row.innerHTML = `
        <td>${escHtml(d.flag)}</td>
        <td><strong>${TMH_MONTH_NAMES[d.month-1]} ${d.year}</strong></td>
        <td>${escHtml(d.name)}</td>
        <td>
          <select class="status-select" onchange="updateStatus('${destId}', this.value)">
            <option value="ready" selected>Ready</option>
            <option value="coming_soon">Coming Soon</option>
          </select>
        </td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-outline" onclick="openEditLinks('${destId}')">Edit Links</button>
          <button class="btn btn-sm btn-archive" onclick="archiveDestination('${destId}', '${escHtml(d.name)}')">Archive</button>
          <button class="btn btn-sm btn-danger" onclick="deleteDestination('${destId}', '${escHtml(d.name)}')">Delete</button>
        </td>`;
      tbody.appendChild(row);
      sortDestinationsTable();

      // Update data
      const existing = TMH_DATA.all_destinations.find(x => x.id === destId);
      if (existing) { existing.status = 'ready'; existing.month = d.month; existing.year = d.year; }
      TMH_DATA.archived_destinations = (TMH_DATA.archived_destinations||[]).filter(x => x.id !== destId);
      if (existing) TMH_DATA.destinations.push(existing);

      closeReinstateModal();
      showToast(`"${d.name}" reinstated for ${TMH_MONTH_NAMES[d.month-1]} ${d.year}.`);
    } else showToast(json.error || "Failed.", true);
  } catch(e) { showToast("Network error.", true); }
  finally {
    if (btn) { btn.disabled = false; btn.textContent = "Reinstate"; }
  }
}

// ─── Edit Links Modal ─────────────────────────────────────

function openEditLinks(destId) {
  const dest = TMH_DATA.all_destinations.find(d => d.id === destId);
  if (!dest) return;

  document.getElementById("edit-links-dest-id").value = destId;
  document.getElementById("edit-links-title").textContent =
    `Edit Links — ${TMH_MONTH_NAMES[dest.month-1]} ${dest.year}: ${dest.name}`;

  const fields = ["social_media", "blog", "canva_guides", "promo_assets"];
  fields.forEach(f => {
    const el = document.getElementById(`el-${f}`);
    if (el) el.value = dest.files?.[f] || "";
  });

  document.getElementById("edit-links-modal").style.display = "flex";
}

function closeEditLinks() {
  document.getElementById("edit-links-modal").style.display = "none";
}

async function saveEditLinks() {
  const destId = document.getElementById("edit-links-dest-id").value;
  const fields = ["social_media", "blog", "canva_guides", "promo_assets"];
  const body = {};
  fields.forEach(f => {
    const el = document.getElementById(`el-${f}`);
    if (el) body[f] = el.value.trim();
  });

  const btn = document.querySelector("#edit-links-modal .btn-primary");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  try {
    const controller = new AbortController();
    const timeout    = setTimeout(() => controller.abort(), 15000);
    const res = await fetch(`/admin/api/destinations/${destId}/files`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: controller.signal
    });
    clearTimeout(timeout);
    let json;
    try { json = await res.json(); } catch(_) { json = {}; }
    if (res.status === 401) {
      window.location.href = "/admin/login?reason=expired";
    } else if (json.success) {
      const dest = TMH_DATA.all_destinations.find(d => d.id === destId);
      if (dest) Object.assign(dest.files, body);
      closeEditLinks();
      showToast("✅ Links saved successfully.");
    } else {
      showToast(json.error || "Save failed — please try again.", true);
    }
  } catch(e) {
    if (e.name === "AbortError") {
      showToast("Save timed out — the server took too long. Please refresh and try again.", true);
    } else {
      showToast("Network error — please check your connection and try again.", true);
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Save Links"; }
  }
}

// ─── Admin: change admin password ────────────────────────

async function changeAdminPassword(e) {
  e.preventDefault();
  const current = document.getElementById("admin-pw-current").value;
  const newPw   = document.getElementById("admin-pw-new").value;
  const confirm = document.getElementById("admin-pw-confirm").value;

  if (newPw !== confirm) { showToast("New passwords don't match.", true); return; }
  if (newPw.length < 6)  { showToast("Password must be at least 6 characters.", true); return; }

  try {
    const res  = await fetch("/admin/api/admin-password", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: current, new_password: newPw })
    });
    const json = await res.json();
    if (json.success) {
      showToast("Admin password updated!");
      document.getElementById("admin-pw-current").value = "";
      document.getElementById("admin-pw-new").value = "";
      document.getElementById("admin-pw-confirm").value = "";
    } else { showToast(json.error || "Failed.", true); }
  } catch(e) { showToast("Network error.", true); }
}

// ─── Admin: save engagement folder URL ───────────────────

async function saveEngagementFolderUrl() {
  const url = (document.getElementById("engagement-folder-url")?.value || "").trim();
  try {
    const res  = await fetch("/admin/api/settings/engagement-folder", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    if (res.status === 401) { window.location.href = "/admin/login?reason=expired"; return; }
    const json = await res.json();
    if (json.success) { showToast("✅ Engagement folder URL saved."); }
    else { showToast(json.error || "Failed.", true); }
  } catch(e) { showToast("Network error.", true); }
}

// ─── Supplier offers — customer ───────────────────────────

async function deleteMyOffer(offerId) {
  if (!confirm("Remove this offer? This cannot be undone.")) return;
  try {
    const res  = await fetch(`/api/offers/${offerId}`, { method: "DELETE" });
    const json = await res.json();
    if (json.success) {
      document.getElementById(`offer-card-${offerId}`)?.remove();
      showToast("Offer removed.");
    } else showToast(json.error || "Failed.", true);
  } catch(e) { showToast("Network error.", true); }
}

// ─── Supplier offers — admin ───────────────────────────────

async function adminDeleteOffer(offerId, customerName) {
  showConfirm(`Delete this offer from ${customerName}? This cannot be undone.`, async () => {
    try {
      const res  = await fetch(`/admin/api/offers/${offerId}`, { method: "DELETE" });
      const json = await res.json();
      if (json.success) {
        document.getElementById(`offer-row-${offerId}`)?.remove();
        showToast("Offer deleted.");
      } else showToast(json.error || "Failed.", true);
    } catch(e) { showToast("Network error.", true); }
  });
}

function filterOffers() {
  const monthVal = document.getElementById("offer-month-filter")?.value || "all";
  const custVal  = document.getElementById("offer-customer-filter")?.value || "all";
  const cards    = document.querySelectorAll("#offers-cards .admin-offer-card");
  let visible = 0;
  cards.forEach(card => {
    const monthMatch = monthVal === "all" || card.dataset.monthKey === monthVal;
    const custMatch  = custVal  === "all" || card.dataset.customerId === custVal;
    const show = monthMatch && custMatch;
    card.style.display = show ? "" : "none";
    if (show) visible++;
  });
  const countEl = document.getElementById("offers-count");
  if (countEl) countEl.textContent = visible === cards.length ? "" : `${visible} of ${cards.length} shown`;
  const emptyMsg = document.getElementById("offers-empty-msg");
  if (emptyMsg) emptyMsg.style.display = visible === 0 ? "" : "none";
}

function copyCaption(elemId) {
  const el = document.getElementById(elemId);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => {
    showToast("Post copy copied to clipboard ✅");
  }).catch(() => {
    // Fallback for older browsers
    const range = document.createRange();
    range.selectNodeContents(el);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand("copy");
    window.getSelection().removeAllRanges();
    showToast("Post copy copied ✅");
  });
}

async function generateReelCopy(offerId) {
  const btn   = document.getElementById(`gen-btn-${offerId}`);
  const panel = document.getElementById(`copy-panel-${offerId}`);
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Generating…'; }
  try {
    const res  = await fetch(`/admin/api/offers/${offerId}/generate-copy`, { method: "POST" });
    let json;
    try { json = await res.json(); } catch(_) { json = {}; }
    if (res.status === 401) { showToast("Session expired — please refresh.", true); return; }
    if (!json.success) { showToast(json.error || "Generation failed.", true); return; }
    const c = json.copy;
    document.getElementById(`copy-headline-${offerId}`).textContent = c.headline || "";
    document.getElementById(`copy-cta-${offerId}`).textContent      = c.cta || "";
    const overlaysEl = document.getElementById(`copy-overlays-${offerId}`);
    overlaysEl.innerHTML = (c.overlays || []).map((line, i) => `
      <div class="generated-copy-row">
        <span class="generated-copy-label">Overlay ${i + 1}</span>
        <span id="copy-ov-${offerId}-${i}" class="generated-copy-value">${escHtml(line)}</span>
        <button class="btn-copy-line" onclick="copyLine('copy-ov-${offerId}-${i}')">Copy</button>
      </div>`).join("");
    if (panel) panel.style.display = "";
    if (btn) btn.textContent = '✨ Regenerate';
    showToast("Reel copy generated ✅");
  } catch(e) {
    showToast("Network error — could not generate copy.", true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function copyLine(elemId) {
  const el = document.getElementById(elemId);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent.trim())
    .then(() => showToast("Copied ✅"))
    .catch(() => showToast("Copy failed", true));
}

function copyAllCopy(offerId) {
  const headline = document.getElementById(`copy-headline-${offerId}`)?.textContent || "";
  const cta      = document.getElementById(`copy-cta-${offerId}`)?.textContent || "";
  const overlays = [];
  let i = 0;
  while (true) {
    const el = document.getElementById(`copy-ov-${offerId}-${i}`);
    if (!el) break;
    overlays.push(el.textContent);
    i++;
  }
  const text = `HEADLINE:\n${headline}\n\nOVERLAY LINES:\n${overlays.join("\n")}\n\nCTA:\n${cta}`;
  navigator.clipboard.writeText(text)
    .then(() => showToast("All copy copied to clipboard ✅"))
    .catch(() => showToast("Copy failed", true));
}

function downloadCopyAsTxt(offerId) {
  const headline = document.getElementById(`copy-headline-${offerId}`)?.textContent || "";
  const cta      = document.getElementById(`copy-cta-${offerId}`)?.textContent || "";
  const overlays = [];
  let i = 0;
  while (true) {
    const el = document.getElementById(`copy-ov-${offerId}-${i}`);
    if (!el) break;
    overlays.push(el.textContent);
    i++;
  }
  const text = `HEADLINE:\n${headline}\n\nOVERLAY LINES:\n${overlays.join("\n")}\n\nCTA:\n${cta}`;
  // Build filename from card DOM (same logic as image ZIP)
  const card   = document.getElementById(`offer-row-${offerId}`);
  const nameEl = card ? card.querySelector('.admin-offer-who strong') : null;
  const metaEl = card ? card.querySelector('.admin-offer-meta') : null;
  const custName = nameEl ? nameEl.textContent.trim().replace(/\s+/g, '-').toLowerCase() : 'customer';
  const month    = metaEl ? metaEl.textContent.split('·')[1]?.trim().replace(/\s+/g, '-') : '';
  const filename = month ? `${custName}-${month}-reel-copy.txt` : `${custName}-reel-copy.txt`;
  const blob = new Blob([text], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
  showToast(`✅ Copy saved as ${filename}`);
}

async function downloadOfferImages(offerId) {
  const card = document.getElementById(`offer-row-${offerId}`);
  if (!card) return;
  const imgs = card.querySelectorAll('.admin-offer-img[data-url]');
  if (!imgs.length) return;
  const btn = card.querySelector('.btn-download-all');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Zipping…'; }
  try {
    const zip = new JSZip();
    const fetches = Array.from(imgs).map(async (img, i) => {
      const url  = img.dataset.url;
      const resp = await fetch(url);
      const blob = await resp.blob();
      const ext  = url.split('?')[0].split('.').pop() || 'jpg';
      zip.file(`image-${i + 1}.${ext}`, blob);
    });
    await Promise.all(fetches);
    const content  = await zip.generateAsync({ type: 'blob' });
    const nameEl   = card.querySelector('.admin-offer-who strong');
    const metaEl   = card.querySelector('.admin-offer-meta');
    const custName = nameEl ? nameEl.textContent.trim().replace(/\s+/g, '-').toLowerCase() : 'customer';
    const month    = metaEl ? metaEl.textContent.split('·')[1]?.trim().replace(/\s+/g, '-') : '';
    const filename = month ? `${custName}-${month}-images.zip` : `${custName}-images.zip`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(content);
    a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    showToast(`✅ ${imgs.length} images downloaded as ZIP`);
  } catch(e) {
    showToast('Download failed — try downloading images individually.', true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '⬇ Download Images'; }
  }
}

async function downloadSingleImage(url, index) {
  try {
    const resp = await fetch(url);
    const blob = await resp.blob();
    const ext  = url.split('?')[0].split('.').pop() || 'jpg';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `image-${index}.${ext}`;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  } catch(e) {
    window.open(url, '_blank'); // fallback — open in new tab
  }
}

function viewCustomerOffers() {
  const custId = document.getElementById("cust-detail-id").value;
  closeCustomerDetail();
  switchTab("offers");
  const custFilter = document.getElementById("offer-customer-filter");
  if (custFilter) { custFilter.value = custId; filterOffers(); }
}

// ─── Refine post copy ─────────────────────────────────────

async function refinePostCopy(offerId) {
  const btn       = document.getElementById(`refine-btn-${offerId}`);
  const captionEl = document.getElementById(`caption-${offerId}`);
  const labelEl   = document.getElementById(`caption-label-${offerId}`);
  const toggleBtn = document.getElementById(`toggle-orig-btn-${offerId}`);
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Refining…'; }
  try {
    const res  = await fetch(`/admin/api/offers/${offerId}/refine-caption`, { method: "POST" });
    let json;
    try { json = await res.json(); } catch(_) { json = {}; }
    if (res.status === 401) { showToast("Session expired — please refresh.", true); return; }
    if (!json.success) { showToast(json.error || "Refinement failed.", true); return; }

    const refined = json.refined_caption;
    // Update data attribute and display
    if (captionEl) {
      captionEl.dataset.refined = refined;
      captionEl.textContent     = refined;
      captionEl.dataset.showing = "refined";  // track state
    }
    if (labelEl)   labelEl.textContent = "Refined Post Copy";
    if (toggleBtn) { toggleBtn.textContent = "Show original"; toggleBtn.dataset.showing = "refined"; toggleBtn.style.display = ""; }
    if (btn)       btn.textContent = "✨ Re-refine";
    showToast("Post copy refined ✅");
  } catch(e) {
    showToast("Network error — could not refine post.", true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function toggleOriginalCaption(offerId) {
  const captionEl = document.getElementById(`caption-${offerId}`);
  const labelEl   = document.getElementById(`caption-label-${offerId}`);
  const toggleBtn = document.getElementById(`toggle-orig-btn-${offerId}`);
  if (!captionEl) return;
  const showing = toggleBtn?.dataset.showing || "refined";
  if (showing === "refined") {
    // Switch to original
    captionEl.textContent = captionEl.dataset.original || "";
    if (labelEl)   labelEl.textContent = "Original Post Copy";
    if (toggleBtn) { toggleBtn.textContent = "Show refined"; toggleBtn.dataset.showing = "original"; }
  } else {
    // Switch back to refined
    captionEl.textContent = captionEl.dataset.refined || "";
    if (labelEl)   labelEl.textContent = "Refined Post Copy";
    if (toggleBtn) { toggleBtn.textContent = "Show original"; toggleBtn.dataset.showing = "refined"; }
  }
}

// ─── Supplier reel slot auto-assignment ──────────────────

const STYLE_NAMES_JS = { 1: "Cinematic", 2: "Bold", 3: "Bright", 4: "Soft" };

function toggleSlotPanel(offerId) {
  const panel = document.getElementById(`slot-panel-${offerId}`);
  const btn   = document.getElementById(`slot-toggle-btn-${offerId}`);
  if (!panel) return;
  const opening = panel.style.display === "none";
  panel.style.display = opening ? "" : "none";
  if (btn) btn.classList.toggle("btn-slot-toggle--open", opening);
}

async function autoAssignSlots(offerId) {
  const panel      = document.getElementById(`slot-panel-${offerId}`);
  const btn        = document.getElementById(`slot-assign-btn-${offerId}`);
  const resultPanel = document.getElementById(`slot-result-${offerId}`);
  const styleRadio  = panel?.querySelector(`input[name="slot-style-${offerId}"]:checked`);
  const assignedStyle = styleRadio ? parseInt(styleRadio.value) : 0;
  if (!assignedStyle) {
    showToast("Pick a reel style first.", true);
    return;
  }
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Classifying images…"; }
  try {
    const res  = await fetch(`/admin/api/offers/${offerId}/auto-assign-slots`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ assigned_style: assignedStyle }),
    });
    let json;
    try { json = await res.json(); } catch(_) { json = {}; }
    if (res.status === 401) { showToast("Session expired — please refresh.", true); return; }
    if (!json.success)      { showToast(json.error || "Auto-assign failed.", true); return; }

    // Render assignment result
    const styleName = STYLE_NAMES_JS[assignedStyle] || "";
    let html = `
      <div class="slot-result-header">
        Style ${assignedStyle} — ${styleName}
        <span class="slot-result-sub">Drag each image into the matching Freepik slot</span>
      </div>
      <div class="slot-result-list">`;
    (json.clips || []).forEach(clip => {
      const slotLabel = clip.slot.replace(/_/g, ' ');
      html += `
        <div class="slot-result-row">
          <span class="slot-result-clip">Slot ${clip.clip}</span>
          <span class="slot-result-slot">${escHtml(slotLabel)}</span>
          ${clip.image_url
            ? `<img src="${escHtml(clip.image_url)}" class="slot-result-thumb" alt="" />`
            : '<span class="slot-result-unassigned">—</span>'}
          <span class="slot-result-desc">
            ${clip.image_num ? `Image ${clip.image_num}` : ''}
            ${clip.description ? ' — ' + escHtml(clip.description) : ''}
          </span>
        </div>`;
    });
    html += `</div>`;

    if (resultPanel) { resultPanel.innerHTML = html; resultPanel.style.display = ""; }

    // Update toggle badge
    const toggleBtn = document.getElementById(`slot-toggle-btn-${offerId}`);
    if (toggleBtn) {
      let badge = toggleBtn.querySelector(".slot-assigned-badge");
      if (!badge) { badge = document.createElement("span"); badge.className = "slot-assigned-badge"; toggleBtn.appendChild(badge); }
      badge.textContent = `Style ${assignedStyle} — ${styleName} ✓`;
    }
    if (btn) btn.textContent = "🤖 Re-assign Slots";
    showToast(`Slots assigned — Style ${assignedStyle} ${styleName} ✅`);
  } catch(e) {
    showToast("Network error — could not auto-assign.", true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ─── Sort destinations table by year then month ──────────

function sortDestinationsTable() {
  const tbody = document.getElementById("destinations-tbody");
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll("tr[data-dest-id]"));
  rows.sort((a, b) => {
    const ya = parseInt(a.dataset.year || 0), ma = parseInt(a.dataset.month || 0);
    const yb = parseInt(b.dataset.year || 0), mb = parseInt(b.dataset.month || 0);
    return ya !== yb ? ya - yb : ma - mb;
  });
  rows.forEach(r => tbody.appendChild(r));
}

// ─── Tab switching ────────────────────────────────────────

function switchTab(name) {
  ["customers","destinations","offers","settings"].forEach(tab => {
    document.getElementById(`tab-${tab}`)?.classList.toggle("tab-btn--active", tab === name);
    document.getElementById(`panel-${tab}`)?.classList.toggle("tab-panel--active", tab === name);
  });
}

// ─── Utility ─────────────────────────────────────────────

function fmtLastLogin(iso) {
  if (!iso) return "Never";
  try {
    const d = new Date(iso + "Z"); // stored as UTC
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}, `
         + `${String(d.getUTCHours()).padStart(2,"0")}:${String(d.getUTCMinutes()).padStart(2,"0")}`;
  } catch(e) { return iso; }
}

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
