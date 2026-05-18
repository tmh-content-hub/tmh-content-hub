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

  // Destination pick
  const pickSection = document.getElementById("cust-detail-pick-section");
  const pickContent = document.getElementById("cust-detail-pick-content");
  if (pickSection && pickContent) {
    const pick = (TMH_DATA.all_picks || []).find(p => p.customer_id === custId);
    if (pick) {
      pickContent.innerHTML = `
        <div style="display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;padding:.6rem .85rem;background:#fff8f0;border:1.5px solid #f5c98a;border-radius:8px;">
          <span style="font-size:1.1rem;">${escHtml(pick.dest_flag)}</span>
          <span style="font-weight:600;">${escHtml(pick.dest_name)}</span>
          <span style="font-size:.8rem;color:#888;">picked ${pick.picked_at ? pick.picked_at.slice(0,10) : ''}</span>
          <button class="btn btn-sm btn-primary" style="margin-left:auto;"
                  onclick="openConfirmPickModal('${escHtml(custId)}','${escHtml(pick.library_id)}','${escHtml(pick.customer_name)}','${escHtml(pick.dest_flag)} ${escHtml(pick.dest_name)}')">
            Confirm + Assign
          </button>
          <button class="btn btn-sm btn-danger"
                  onclick="dismissPick('${escHtml(custId)}','${escHtml(pick.dest_name)}')">
            Dismiss
          </button>
        </div>`;
    } else {
      pickContent.innerHTML = '<span style="color:#aaa;font-size:.85rem;">No pending pick from this customer.</span>';
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

// ─── Auto-flag emoji lookup ───────────────────────────────

const DEST_FLAG_LOOKUP = {
  // Countries (common names → ISO 3166-1 alpha-2)
  "afghanistan":"AF","albania":"AL","algeria":"DZ","andorra":"AD","angola":"AO",
  "antigua":"AG","antigua and barbuda":"AG","argentina":"AR","armenia":"AM",
  "australia":"AU","austria":"AT","azerbaijan":"AZ","bahamas":"BS","the bahamas":"BS",
  "bahrain":"BH","bangladesh":"BD","barbados":"BB","belarus":"BY","belgium":"BE",
  "belize":"BZ","benin":"BJ","bhutan":"BT","bolivia":"BO","bosnia":"BA",
  "bosnia and herzegovina":"BA","botswana":"BW","brazil":"BR","brunei":"BN",
  "bulgaria":"BG","burkina faso":"BF","burundi":"BI","cambodia":"KH","cameroon":"CM",
  "canada":"CA","cape verde":"CV","central african republic":"CF","chad":"TD",
  "chile":"CL","china":"CN","colombia":"CO","comoros":"KM","congo":"CG",
  "democratic republic of congo":"CD","dr congo":"CD","costa rica":"CR","croatia":"HR",
  "cuba":"CU","cyprus":"CY","czech republic":"CZ","czechia":"CZ","denmark":"DK",
  "djibouti":"DJ","dominica":"DM","dominican republic":"DO","ecuador":"EC","egypt":"EG",
  "el salvador":"SV","equatorial guinea":"GQ","eritrea":"ER","estonia":"EE",
  "eswatini":"SZ","swaziland":"SZ","ethiopia":"ET","fiji":"FJ","finland":"FI",
  "france":"FR","gabon":"GA","gambia":"GM","the gambia":"GM","georgia":"GE",
  "germany":"DE","ghana":"GH","greece":"GR","grenada":"GD","guatemala":"GT",
  "guinea":"GN","guinea-bissau":"GW","guyana":"GY","haiti":"HT","honduras":"HN",
  "hungary":"HU","iceland":"IS","india":"IN","indonesia":"ID","iran":"IR","iraq":"IQ",
  "ireland":"IE","israel":"IL","italy":"IT","ivory coast":"CI","côte d'ivoire":"CI",
  "jamaica":"JM","japan":"JP","jordan":"JO","kazakhstan":"KZ","kenya":"KE",
  "kiribati":"KI","north korea":"KP","south korea":"KR","korea":"KR","kosovo":"XK",
  "kuwait":"KW","kyrgyzstan":"KG","laos":"LA","latvia":"LV","lebanon":"LB",
  "lesotho":"LS","liberia":"LR","libya":"LY","liechtenstein":"LI","lithuania":"LT",
  "luxembourg":"LU","madagascar":"MG","malawi":"MW","malaysia":"MY","maldives":"MV",
  "mali":"ML","malta":"MT","marshall islands":"MH","mauritania":"MR","mauritius":"MU",
  "mexico":"MX","micronesia":"FM","moldova":"MD","monaco":"MC","mongolia":"MN",
  "montenegro":"ME","morocco":"MA","mozambique":"MZ","myanmar":"MM","burma":"MM",
  "namibia":"NA","nauru":"NR","nepal":"NP","netherlands":"NL","new zealand":"NZ",
  "nicaragua":"NI","niger":"NE","nigeria":"NG","north macedonia":"MK","norway":"NO",
  "oman":"OM","pakistan":"PK","palau":"PW","panama":"PA","papua new guinea":"PG",
  "paraguay":"PY","peru":"PE","philippines":"PH","poland":"PL","portugal":"PT",
  "qatar":"QA","romania":"RO","russia":"RU","rwanda":"RW","saint kitts":"KN",
  "saint kitts and nevis":"KN","saint lucia":"LC","saint vincent":"VC",
  "samoa":"WS","san marino":"SM","sao tome":"ST","saudi arabia":"SA","senegal":"SN",
  "serbia":"RS","seychelles":"SC","sierra leone":"SL","singapore":"SG","slovakia":"SK",
  "slovenia":"SI","solomon islands":"SB","somalia":"SO","south africa":"ZA",
  "south sudan":"SS","spain":"ES","sri lanka":"LK","sudan":"SD","suriname":"SR",
  "sweden":"SE","switzerland":"CH","syria":"SY","taiwan":"TW","tajikistan":"TJ",
  "tanzania":"TZ","thailand":"TH","timor-leste":"TL","east timor":"TL","togo":"TG",
  "tonga":"TO","trinidad":"TT","trinidad and tobago":"TT","tunisia":"TN","turkey":"TR",
  "türkiye":"TR","turkmenistan":"TM","tuvalu":"TV","uganda":"UG","ukraine":"UA",
  "united arab emirates":"AE","uae":"AE","united kingdom":"GB","uk":"GB",
  "united states":"US","usa":"US","united states of america":"US","uruguay":"UY",
  "uzbekistan":"UZ","vanuatu":"VU","venezuela":"VE","vietnam":"VN","viet nam":"VN",
  "yemen":"YE","zambia":"ZM","zimbabwe":"ZW",

  // UK / British Isles
  "england":"GB","scotland":"GB","wales":"GB","northern ireland":"GB",

  // Popular travel regions / cities / islands mapped to their country
  "bali":"ID","java":"ID","lombok":"ID","komodo":"ID","flores":"ID",
  "cancun":"MX","tulum":"MX","cabo":"MX","cabo san lucas":"MX","playa del carmen":"MX",
  "mexico city":"MX","oaxaca":"MX","puerto vallarta":"MX","guadalajara":"MX",
  "santorini":"GR","mykonos":"GR","athens":"GR","crete":"GR","corfu":"GR",
  "rhodes":"GR","zakynthos":"GR","zante":"GR","kefalonia":"GR","thessaloniki":"GR",
  "canary islands":"ES","tenerife":"ES","lanzarote":"ES","gran canaria":"ES",
  "fuerteventura":"ES","ibiza":"ES","mallorca":"ES","majorca":"ES","menorca":"ES",
  "barcelona":"ES","madrid":"ES","seville":"ES","granada":"ES","valencia":"ES",
  "costa del sol":"ES","costa brava":"ES","marbella":"ES",
  "paris":"FR","nice":"FR","provence":"FR","normandy":"FR","french riviera":"FR",
  "côte d'azur":"FR","lyon":"FR","bordeaux":"FR","mont saint-michel":"FR",
  "rome":"IT","venice":"IT","florence":"IT","milan":"IT","naples":"IT",
  "tuscany":"IT","amalfi coast":"IT","amalfi":"IT","sicily":"IT","sardinia":"IT",
  "positano":"IT","cinque terre":"IT","capri":"IT","lake como":"IT","pompeii":"IT",
  "dubai":"AE","abu dhabi":"AE","sharjah":"AE",
  "maldives":"MV","male":"MV",
  "prague":"CZ","brno":"CZ",
  "budapest":"HU",
  "amsterdam":"NL",
  "lisbon":"PT","porto":"PT","algarve":"PT","madeira":"PT","azores":"PT",
  "london":"GB","edinburgh":"GB","dublin":"IE","galway":"IE",
  "new york":"US","miami":"US","los angeles":"US","san francisco":"US",
  "hawaii":"US","maui":"US","honolulu":"US","new orleans":"US","las vegas":"US",
  "orlando":"US","chicago":"US","boston":"US",
  "toronto":"CA","vancouver":"CA","montreal":"CA","banff":"CA","jasper":"CA",
  "tokyo":"JP","kyoto":"JP","osaka":"JP","hiroshima":"JP","hokkaido":"JP",
  "seoul":"KR","busan":"KR","jeju":"KR",
  "bangkok":"TH","chiang mai":"TH","phuket":"TH","koh samui":"TH","koh tao":"TH",
  "pattaya":"TH","phi phi islands":"TH",
  "singapore":"SG",
  "kuala lumpur":"MY","penang":"MY","langkawi":"MY","borneo":"MY",
  "ho chi minh city":"VN","saigon":"VN","hanoi":"VN","ha long bay":"VN",
  "hoi an":"VN","da nang":"VN","sapa":"VN",
  "siem reap":"KH","angkor":"KH","phnom penh":"KH",
  "beijing":"CN","shanghai":"CN","hong kong":"HK","macau":"MO",
  "sydney":"AU","melbourne":"AU","gold coast":"AU","cairns":"AU",
  "great barrier reef":"AU","uluru":"AU","perth":"AU","byron bay":"AU",
  "queenstown":"NZ","auckland":"NZ","rotorua":"NZ","fiordland":"NZ",
  "cape town":"ZA","johannesburg":"ZA","kruger":"ZA","safari":"ZA",
  "marrakech":"MA","marrakesh":"MA","fes":"MA","fez":"MA","casablanca":"MA",
  "cairo":"EG","luxor":"EG","aswan":"EG","sharm el sheikh":"EG","hurghada":"EG",
  "nairobi":"KE","masai mara":"KE","serengeti":"TZ","zanzibar":"TZ","kilimanjaro":"TZ",
  "dar es salaam":"TZ","arusha":"TZ",
  "istanbul":"TR","cappadocia":"TR","ankara":"TR","bodrum":"TR","antalya":"TR",
  "ephesus":"TR","pamukkale":"TR",
  "reykjavik":"IS","blue lagoon":"IS","northern lights":"IS",
  "oslo":"NO","bergen":"NO","fjords":"NO","tromsø":"NO",
  "stockholm":"SE","gothenburg":"SE","malmö":"SE",
  "copenhagen":"DK","faroe islands":"FO",
  "helsinki":"FI","lapland":"FI",
  "vienna":"AT","salzburg":"AT","innsbruck":"AT",
  "zurich":"CH","geneva":"CH","bern":"CH","interlaken":"CH","lucerne":"CH",
  "brussels":"BE","bruges":"BE","ghent":"BE",
  "warsaw":"PL","krakow":"PL","kraków":"PL","gdansk":"PL",
  "bucharest":"RO","transylvania":"RO","bran":"RO",
  "moscow":"RU","saint petersburg":"RU","st petersburg":"RU",
  "riga":"LV","tallinn":"EE","vilnius":"LT",
  "zagreb":"HR","dubrovnik":"HR","split":"HR","plitvice":"HR","hvar":"HR",
  "kotor":"ME","podgorica":"ME","budva":"ME",
  "tirana":"AL","berat":"AL","gjirokastër":"AL",
  "skopje":"MK","ohrid":"MK",
  "sofia":"BG","plovdiv":"BG",
  "belgrade":"RS","novi sad":"RS",
  "sarajevo":"BA","mostar":"BA",
  "valletta":"MT","gozo":"MT",
  "nicosia":"CY","paphos":"CY","limassol":"CY",
  "lima":"PE","machu picchu":"PE","cusco":"PE","amazon":"PE",
  "rio de janeiro":"BR","rio":"BR","são paulo":"BR","sao paulo":"BR",
  "iguazu falls":"AR","iguassu falls":"BR","buenos aires":"AR","patagonia":"AR",
  "santiago":"CL","atacama":"CL","torres del paine":"CL",
  "bogota":"CO","cartagena":"CO","medellín":"CO","medellin":"CO",
  "quito":"EC","galapagos":"EC","galápagos":"EC",
  "havana":"CU","trinidad cuba":"CU",
  "san jose":"CR","costa rica":"CR",
  "panama city":"PA",
  "belize city":"BZ","belize barrier reef":"BZ",
  "montego bay":"JM","kingston":"JM","negril":"JM",
  "bridgetown":"BB","st lucia":"LC","saint lucia":"LC","barbados":"BB",
  "nassau":"BS","bahamas":"BS","turks and caicos":"TC",
  "punta cana":"DO","santo domingo":"DO",
  "san juan":"PR","puerto rico":"PR",
  "colombo":"LK","galle":"LK",
  "kathmandu":"NP","everest":"NP","pokhara":"NP",
  "delhi":"IN","mumbai":"IN","goa":"IN","rajasthan":"IN","agra":"IN",
  "jaipur":"IN","varanasi":"IN","kerala":"IN","jaisalmer":"IN","udaipur":"IN",
  "colombo":"LK","galle":"LK","kandy":"LK",
  "muscat":"OM","nizwa":"OM",
  "doha":"QA",
  "amman":"JO","petra":"JO","wadi rum":"JO",
  "tel aviv":"IL","jerusalem":"IL","dead sea":"IL",
  "beirut":"LB",
  "yerevan":"AM","armenia":"AM",
  "tbilisi":"GE","batumi":"GE",
  "baku":"AZ",
  "tashkent":"UZ","samarkand":"UZ",
  "almaty":"KZ","nur-sultan":"KZ","astana":"KZ",
  "ulaanbaatar":"MN",
  "phnom penh":"KH","siem reap":"KH",
  "vientiane":"LA","luang prabang":"LA",
  "yangon":"MM","bagan":"MM","inle lake":"MM",
  "cebu":"PH","palawan":"PH","boracay":"PH","manila":"PH","el nido":"PH",
  "coron":"PH",
  "colombo":"LK",
  "malé":"MV","maldives":"MV",
  "port louis":"MU","mauritius":"MU",
  "victoria seychelles":"SC","seychelles":"SC","mahé":"SC","praslin":"SC",
  "antananarivo":"MG","nosy be":"MG",
  "lusaka":"ZM","livingstone":"ZM","victoria falls":"ZM",
  "harare":"ZW","hwange":"ZW","victoria falls zimbabwe":"ZW",
  "accra":"GH",
  "lagos":"NG","abuja":"NG",
  "dakar":"SN",
  "addis ababa":"ET","lalibela":"ET",
  "kigali":"RW",
  "kampala":"UG","bwindi":"UG",
  "dar es salaam":"TZ",
  "windhoek":"NA","sossusvlei":"NA","etosha":"NA",
  "gaborone":"BW","okavango":"BW","chobe":"BW",
  "victoria falls zambia":"ZM",
  "tunis":"TN","djerba":"TN","sousse":"TN","hammamet":"TN",
  "algiers":"DZ",
  "tripoli":"LY",
  "khartoum":"SD",
  "porto novo":"BJ","cotonou":"BJ",
  "lome":"TG",
  "abidjan":"CI",
  "new caledonia":"NC","noumea":"NC",
  "tahiti":"PF","bora bora":"PF","french polynesia":"PF","moorea":"PF",
  "cook islands":"CK","rarotonga":"CK",
  "vanuatu":"VU","port vila":"VU",
  "tonga":"TO","nuku'alofa":"TO",
  "samoa":"WS","apia":"WS",
  "fiji":"FJ","nadi":"FJ","suva":"FJ",
  "palau":"PW","koror":"PW",
  "guam":"GU",
  "northern mariana islands":"MP",
};

function isoToFlag(iso) {
  if (!iso || iso.length !== 2) return "";
  return [...iso.toUpperCase()].map(c =>
    String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65)
  ).join("");
}

function autoSuggestFlag(nameInputId, flagInputId) {
  const nameEl = document.getElementById(nameInputId);
  const flagEl = document.getElementById(flagInputId);
  if (!nameEl || !flagEl) return;

  // Only fill if flag field is currently empty
  if (flagEl.value.trim() !== "") return;

  const raw = nameEl.value.trim().toLowerCase();
  if (!raw) return;

  // 1. Exact match
  let iso = DEST_FLAG_LOOKUP[raw];

  // 2. Starts-with match (longest key that matches)
  if (!iso) {
    let bestKey = "";
    for (const key of Object.keys(DEST_FLAG_LOOKUP)) {
      if (raw.startsWith(key) && key.length > bestKey.length) bestKey = key;
    }
    if (bestKey) iso = DEST_FLAG_LOOKUP[bestKey];
  }

  // 3. Contains match (first key found that the raw name contains)
  if (!iso) {
    for (const key of Object.keys(DEST_FLAG_LOOKUP)) {
      if (raw.includes(key)) { iso = DEST_FLAG_LOOKUP[key]; break; }
    }
  }

  if (iso) flagEl.value = isoToFlag(iso);
}

// Attach auto-flag listeners once DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // Add library form
  const libName = document.getElementById("lib-name");
  if (libName) {
    libName.addEventListener("blur", () => autoSuggestFlag("lib-name", "lib-flag"));
  }

  // Edit library modal — attach on focus-out
  const editLibName = document.getElementById("edit-lib-name");
  if (editLibName) {
    editLibName.addEventListener("blur", () => autoSuggestFlag("edit-lib-name", "edit-lib-flag"));
  }
});

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

// ─────────────────────────────────────────────
// Destination Library
// ─────────────────────────────────────────────

async function addLibraryDest(e) {
  e.preventDefault();
  const name  = document.getElementById("lib-name").value.trim();
  const flag  = document.getElementById("lib-flag").value.trim() || "🌍";
  const notes = document.getElementById("lib-notes").value.trim();
  if (!name) { showToast("Please enter a destination name.", true); return; }
  try {
    const res  = await fetch("/admin/api/library", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({name, flag, notes})
    });
    const json = await res.json();
    if (json.success) {
      showToast(`"${name}" added to library.`);
      const item = json.item;
      TMH_DATA.library = TMH_DATA.library || [];
      TMH_DATA.library.push(item);

      const tbody = document.getElementById("library-tbody");
      const empty = tbody.querySelector(".empty-cell");
      if (empty) empty.closest("tr").remove();

      const row = document.createElement("tr");
      row.id = `lib-row-${item.id}`;
      row.setAttribute("data-lib-id", item.id);
      row.innerHTML = libraryRowHtml(item);
      tbody.appendChild(row);

      document.getElementById("lib-name").value  = "";
      document.getElementById("lib-flag").value  = "";
      document.getElementById("lib-notes").value = "";

      // Refresh poll modal checkboxes
      refreshPollCheckboxes();
    } else { showToast(json.error || "Failed to add.", true); }
  } catch(err) { showToast("Network error.", true); }
}

function libraryRowHtml(item) {
  const hasLinks = item.social_media || item.blog || item.canva_guides || item.promo_assets;
  return `
    <td>${escHtml(item.flag)}</td>
    <td><strong>${escHtml(item.name)}</strong></td>
    <td style="color:#888;font-size:.85rem;">${escHtml(item.notes) || '—'}</td>
    <td style="font-size:.8rem;">${hasLinks
      ? '<span style="color:var(--green,#2ecc71);">✓ Links added</span>'
      : '<span style="color:#ccc;">No links yet</span>'}</td>
    <td class="actions-cell">
      <button class="btn btn-sm btn-outline" onclick="openEditLibrary('${item.id}','${escHtml(item.name)}','${escHtml(item.flag)}','${escHtml(item.social_media||'')}','${escHtml(item.blog||'')}','${escHtml(item.canva_guides||'')}','${escHtml(item.promo_assets||'')}','${escHtml(item.notes||'')}')">Edit</button>
      <button class="btn btn-sm btn-primary" onclick="openScheduleModal('${item.id}','${escHtml(item.name)}')">📅 Schedule</button>
      <button class="btn btn-sm btn-outline" onclick="openAssignCustomerModal('${item.id}','${escHtml(item.name)}')">👤 Assign</button>
      <button class="btn btn-sm btn-danger" onclick="deleteLibraryDest('${item.id}','${escHtml(item.name)}')">Delete</button>
    </td>`;
}

function openEditLibrary(id, name, flag, social, blog, canva, promo, notes) {
  document.getElementById("edit-lib-id").value     = id;
  document.getElementById("edit-lib-name").value   = name;
  document.getElementById("edit-lib-flag").value   = flag;
  document.getElementById("edit-lib-social").value = social;
  document.getElementById("edit-lib-blog").value   = blog;
  document.getElementById("edit-lib-canva").value  = canva;
  document.getElementById("edit-lib-promo").value  = promo;
  document.getElementById("edit-lib-notes").value  = notes;
  document.getElementById("edit-library-modal").style.display = "flex";
}

function closeEditLibrary() {
  document.getElementById("edit-library-modal").style.display = "none";
}

async function saveLibraryEdit() {
  const id   = document.getElementById("edit-lib-id").value;
  const name = document.getElementById("edit-lib-name").value.trim();
  if (!name) { showToast("Name required.", true); return; }
  const body = {
    name,
    flag:         document.getElementById("edit-lib-flag").value.trim() || "🌍",
    social_media: document.getElementById("edit-lib-social").value.trim(),
    blog:         document.getElementById("edit-lib-blog").value.trim(),
    canva_guides: document.getElementById("edit-lib-canva").value.trim(),
    promo_assets: document.getElementById("edit-lib-promo").value.trim(),
    notes:        document.getElementById("edit-lib-notes").value.trim(),
  };
  try {
    const res  = await fetch(`/admin/api/library/${id}`, {
      method: "PUT", headers: {"Content-Type":"application/json"},
      body: JSON.stringify(body)
    });
    const json = await res.json();
    if (json.success) {
      showToast(`"${name}" updated.`);
      closeEditLibrary();
      // Update row in DOM
      const row = document.getElementById(`lib-row-${id}`);
      if (row) {
        const updated = {...body, id};
        row.innerHTML = libraryRowHtml(updated);
      }
      // Update in-memory data
      if (TMH_DATA.library) {
        const idx = TMH_DATA.library.findIndex(l => l.id === id);
        if (idx >= 0) TMH_DATA.library[idx] = {...TMH_DATA.library[idx], ...body};
      }
      refreshPollCheckboxes();
    } else { showToast(json.error || "Failed.", true); }
  } catch(err) { showToast("Network error.", true); }
}

async function deleteLibraryDest(id, name) {
  showConfirm(`Delete "${name}" from the library? This cannot be undone.`, async () => {
    try {
      const res  = await fetch(`/admin/api/library/${id}`, {method:"DELETE"});
      const json = await res.json();
      if (json.success) {
        document.getElementById(`lib-row-${id}`)?.remove();
        if (TMH_DATA.library) TMH_DATA.library = TMH_DATA.library.filter(l => l.id !== id);
        showToast(`"${name}" removed from library.`);
        refreshPollCheckboxes();
      } else { showToast(json.error || "Failed.", true); }
    } catch(err) { showToast("Network error.", true); }
  });
}

// ─────────────────────────────────────────────
// Schedule library destination to month
// ─────────────────────────────────────────────

function openScheduleModal(libId, libName) {
  document.getElementById("schedule-lib-id").value   = libId;
  document.getElementById("schedule-lib-name").textContent = libName;
  document.getElementById("schedule-modal").style.display = "flex";
}

function closeScheduleModal() {
  document.getElementById("schedule-modal").style.display = "none";
}

async function submitSchedule() {
  const libId  = document.getElementById("schedule-lib-id").value;
  const month  = parseInt(document.getElementById("schedule-month").value);
  const year   = parseInt(document.getElementById("schedule-year").value);
  const status = document.getElementById("schedule-status").value;
  try {
    const res  = await fetch("/admin/api/schedule", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({library_id: libId, month, year, status})
    });
    const json = await res.json();
    if (json.success) {
      const d = json.destination;
      showToast(`${TMH_MONTH_NAMES[month-1]} ${year} scheduled as "${d.name}".`);
      closeScheduleModal();

      // Update or add row in schedule table
      const tbody = document.getElementById("destinations-tbody");
      let existingRow = null;
      tbody.querySelectorAll("tr").forEach(tr => {
        if (parseInt(tr.getAttribute("data-month")) === month &&
            parseInt(tr.getAttribute("data-year"))  === year) {
          existingRow = tr;
        }
      });

      const rowHtml = `
        <td>${escHtml(d.flag)}</td>
        <td><strong>${TMH_MONTH_NAMES[month-1]} ${year}</strong></td>
        <td>${escHtml(d.name)}</td>
        <td>
          <select class="status-select" onchange="updateStatus('${d.id}', this.value)">
            <option value="ready" ${status==='ready'?'selected':''}>Ready</option>
            <option value="coming_soon" ${status==='coming_soon'?'selected':''}>Coming Soon</option>
          </select>
        </td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-outline" onclick="openEditLinks('${d.id}')">Edit Links</button>
          <button class="btn btn-sm btn-archive" onclick="archiveDestination('${d.id}','${escHtml(d.name)}')">Archive</button>
          <button class="btn btn-sm btn-danger" onclick="deleteDestination('${d.id}','${escHtml(d.name)}')">Delete</button>
        </td>`;

      if (existingRow) {
        existingRow.id = `dest-row-${d.id}`;
        existingRow.setAttribute("data-dest-id", d.id);
        existingRow.innerHTML = rowHtml;
      } else {
        const empty = tbody.querySelector(".empty-cell");
        if (empty) empty.closest("tr").remove();
        const row = document.createElement("tr");
        row.id = `dest-row-${d.id}`;
        row.setAttribute("data-dest-id", d.id);
        row.setAttribute("data-month", month);
        row.setAttribute("data-year", year);
        row.innerHTML = rowHtml;
        tbody.appendChild(row);
        sortDestinationsTable();
      }

      // Update in-memory data
      const newDest = {id:d.id, name:d.name, flag:d.flag, month, year, status,
                       files:{social_media:"",blog:"",canva_guides:"",promo_assets:"",reels:""}};
      const idx = TMH_DATA.destinations.findIndex(x => x.month === month && x.year === year);
      if (idx >= 0) TMH_DATA.destinations[idx] = newDest;
      else TMH_DATA.destinations.push(newDest);
    } else { showToast(json.error || "Failed.", true); }
  } catch(err) { showToast("Network error.", true); }
}

// ─────────────────────────────────────────────
// Assign destination to customer (override)
// ─────────────────────────────────────────────

function openAssignCustomerModal(libId, libName) {
  document.getElementById("assign-lib-id").value = libId;
  document.getElementById("assign-lib-name").textContent = libName;
  document.getElementById("assign-customer-modal").style.display = "flex";
}

function closeAssignCustomerModal() {
  document.getElementById("assign-customer-modal").style.display = "none";
}

async function submitAssignCustomer() {
  const libId      = document.getElementById("assign-lib-id").value;
  const customerId = document.getElementById("assign-customer-select").value;
  const month      = parseInt(document.getElementById("assign-month").value);
  const year       = parseInt(document.getElementById("assign-year").value);
  try {
    const res  = await fetch("/admin/api/overrides", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({customer_id: customerId, library_id: libId, month, year, confirmed: true})
    });
    const json = await res.json();
    if (json.success) {
      const ov = json.override;
      showToast(`${ov.dest_flag} ${ov.dest_name} assigned to ${ov.customer_name} for ${TMH_MONTH_NAMES[month-1]} ${year}.`);
      closeAssignCustomerModal();
      // Add row to overrides table
      addOverrideRow(ov);
    } else { showToast(json.error || "Failed.", true); }
  } catch(err) { showToast("Network error.", true); }
}

function addOverrideRow(ov) {
  // Insert into overrides section if it's visible on the page
  const tables = document.querySelectorAll(".panel-section table");
  tables.forEach(t => {
    const headerCells = Array.from(t.querySelectorAll("th")).map(th => th.textContent.trim());
    if (headerCells.includes("Customer") && headerCells.includes("Month") && headerCells.includes("Destination")) {
      const noOverrides = t.querySelector(".empty-cell");
      // Just reload the page to keep things simple for overrides
    }
  });
  // Simplest approach: page reload so overrides section updates correctly
  showToast("Assignment saved — reloading…");
  setTimeout(() => window.location.reload(), 1200);
}

async function confirmOverride(overrideId) {
  try {
    const res  = await fetch(`/admin/api/overrides/${overrideId}/confirm`, {method:"PUT"});
    const json = await res.json();
    if (json.success) {
      showToast("Override confirmed.");
      const row = document.getElementById(`override-row-${overrideId}`);
      if (row) {
        // Replace the pending cell with confirmed badge
        const statusCell = row.cells[3];
        const actionsCell = row.cells[4];
        if (statusCell) statusCell.innerHTML = '<span style="color:var(--green,#2ecc71);font-weight:600;">Confirmed</span>';
        if (actionsCell) {
          // Remove the confirm button, keep delete
          const confirmBtn = actionsCell.querySelector('.btn-primary');
          if (confirmBtn) confirmBtn.remove();
        }
      }
    } else { showToast(json.error || "Failed.", true); }
  } catch(err) { showToast("Network error.", true); }
}

async function confirmOverrideFromPick(customerId, libId, month, year) {
  try {
    const res  = await fetch("/admin/api/overrides", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({customer_id: customerId, library_id: libId, month, year, confirmed: true})
    });
    const json = await res.json();
    if (json.success) {
      showToast("Destination confirmed for customer.");
      setTimeout(() => window.location.reload(), 1200);
    } else { showToast(json.error || "Failed.", true); }
  } catch(err) { showToast("Network error.", true); }
}

async function deleteOverride(overrideId) {
  showConfirm("Remove this destination override for this customer?", async () => {
    try {
      const res  = await fetch(`/admin/api/overrides/${overrideId}`, {method:"DELETE"});
      const json = await res.json();
      if (json.success) {
        document.getElementById(`override-row-${overrideId}`)?.remove();
        showToast("Override removed.");
      } else { showToast(json.error || "Failed.", true); }
    } catch(err) { showToast("Network error.", true); }
  });
}

// ─────────────────────────────────────────────
// Available for choice toggle
// ─────────────────────────────────────────────

async function toggleAvailable(libId, makeAvailable) {
  try {
    const res  = await fetch(`/admin/api/library/${libId}/available`, {
      method: "PUT", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({available: makeAvailable})
    });
    const json = await res.json();
    if (json.success) {
      showToast(makeAvailable
        ? "Destination is now available for customers to choose."
        : "Destination removed from customer choices.");
      // Update the label text next to the checkbox
      const row = document.getElementById(`lib-row-${libId}`);
      if (row) {
        const label = row.querySelector(".available-toggle-label");
        if (label) label.textContent = makeAvailable ? "Available ✓" : "Off";
      }
      // Update in-memory data
      if (TMH_DATA.library) {
        const item = TMH_DATA.library.find(l => l.id === libId);
        if (item) item.available_for_choice = makeAvailable;
      }
    } else {
      showToast(json.error || "Failed.", true);
      // Revert checkbox
      const cb = document.querySelector(`.available-checkbox[data-lib-id="${libId}"]`);
      if (cb) cb.checked = !makeAvailable;
    }
  } catch(err) {
    showToast("Network error.", true);
    const cb = document.querySelector(`.available-checkbox[data-lib-id="${libId}"]`);
    if (cb) cb.checked = !makeAvailable;
  }
}

// ─────────────────────────────────────────────
// Confirm customer pick + assign month
// ─────────────────────────────────────────────

function openConfirmPickModal(customerId, libId, customerName, destLabel) {
  document.getElementById("confirm-pick-customer-id").value      = customerId;
  document.getElementById("confirm-pick-library-id").value       = libId;
  document.getElementById("confirm-pick-customer-name").textContent = customerName;
  document.getElementById("confirm-pick-dest-name").textContent  = destLabel;
  document.getElementById("confirm-pick-modal").style.display    = "flex";
}

function closeConfirmPickModal() {
  document.getElementById("confirm-pick-modal").style.display = "none";
}

async function submitConfirmPick() {
  const customerId = document.getElementById("confirm-pick-customer-id").value;
  const libId      = document.getElementById("confirm-pick-library-id").value;
  const month      = parseInt(document.getElementById("confirm-pick-month").value);
  const year       = parseInt(document.getElementById("confirm-pick-year").value);
  try {
    const res  = await fetch("/admin/api/overrides", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({customer_id: customerId, library_id: libId, month, year, confirmed: true})
    });
    const json = await res.json();
    if (json.success) {
      await fetch(`/admin/api/picks/${customerId}`, {method:"DELETE"});
      // Remove from in-memory data
      if (TMH_DATA.all_picks) {
        TMH_DATA.all_picks = TMH_DATA.all_picks.filter(p => p.customer_id !== customerId);
      }
      closeConfirmPickModal();
      // Update the pick section in the customer detail modal
      const pickContent = document.getElementById("cust-detail-pick-content");
      if (pickContent) {
        pickContent.innerHTML = `<span style="color:#2ecc71;font-size:.85rem;font-weight:600;">✓ Assigned to ${TMH_MONTH_NAMES[month-1]} ${year}</span>`;
      }
      showToast(`Destination assigned for ${TMH_MONTH_NAMES[month-1]} ${year}. Customer will see it live.`);
      setTimeout(() => window.location.reload(), 1800);
    } else { showToast(json.error || "Failed.", true); }
  } catch(err) { showToast("Network error.", true); }
}

async function dismissPick(customerId, destName) {
  showConfirm(`Dismiss this pick? The customer will be able to choose again.`, async () => {
    try {
      const res  = await fetch(`/admin/api/picks/${customerId}`, {method:"DELETE"});
      const json = await res.json();
      if (json.success) {
        // Remove from in-memory data
        if (TMH_DATA.all_picks) {
          TMH_DATA.all_picks = TMH_DATA.all_picks.filter(p => p.customer_id !== customerId);
        }
        // Update pick section in open modal
        const pickContent = document.getElementById("cust-detail-pick-content");
        if (pickContent) {
          pickContent.innerHTML = '<span style="color:#aaa;font-size:.85rem;">No pending pick from this customer.</span>';
        }
        showToast("Pick dismissed — customer can choose again.");
      } else { showToast(json.error || "Failed.", true); }
    } catch(err) { showToast("Network error.", true); }
  });
}
