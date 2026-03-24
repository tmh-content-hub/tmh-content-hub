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
  document.getElementById("cust-detail-id").value        = custId;
  document.getElementById("cust-detail-title").textContent = cust.name;
  document.getElementById("cust-detail-email").textContent = cust.email;
  document.getElementById("cust-detail-joined").textContent = cust.joined_date || "—";
  document.getElementById("cust-detail-notes").value     = cust.notes || "";
  renderAssignedList(cust);
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
    for (const destId of [...(cust.assigned_dest_ids || [])]) {
      await fetch(`/admin/api/customers/${custId}/unassign`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dest_id: destId })
      });
    }
    cust.assigned_dest_ids = [];
    renderAssignedList(cust);
    updateCustomerBadge(custId, []);
    showToast("All assignments cleared.");
  });
}

function updateCustomerBadge(custId, ids) {
  const row = document.getElementById(`cust-row-${custId}`);
  if (!row) return;
  const cell = row.querySelectorAll("td")[3];
  if (!cell) return;
  cell.innerHTML = ids.length > 0
    ? `<span class="badge badge--assigned">${ids.length} assigned</span>`
    : `<span style="color:#888;font-size:.85rem;">Rolling window</span>`;
}

async function saveCustomerNotes() {
  const custId = document.getElementById("cust-detail-id").value;
  const notes  = document.getElementById("cust-detail-notes").value;
  try {
    const res  = await fetch(`/admin/api/customers/${custId}/notes`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes })
    });
    const json = await res.json();
    if (json.success) {
      const cust = TMH_DATA.customers.find(c => c.id === custId);
      if (cust) cust.notes = notes;
      closeCustomerDetail();
      showToast("Notes saved.");
    } else { showToast(json.error || "Failed.", true); }
  } catch(e) { showToast("Network error.", true); }
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
        <td><span style="color:#888;font-size:.85rem;">Rolling window</span></td>
        <td class="actions-cell">
          <button class="btn btn-sm btn-outline" onclick="resetPassword('${json.customer.id}', '${escHtml(json.customer.name)}')">Reset pw</button>
          <button class="btn btn-sm btn-danger" onclick="deleteCustomer('${json.customer.id}', '${escHtml(json.customer.name)}')">Delete</button>
        </td>`;
      tbody.appendChild(row);

      TMH_DATA.customers.push({
        id: json.customer.id, name, email,
        joined_date: json.customer.joined_date, notes: "", assigned_dest_ids: []
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

  const fields = ["blog_docx","social_posts","promo_assets","guide_pdf",
                  "images_folder","canva_guide","canva_carousel","canva_pinterest"];
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
  const fields = ["blog_docx","social_posts","promo_assets","guide_pdf",
                  "images_folder","canva_guide","canva_carousel","canva_pinterest"];
  const body = {};
  fields.forEach(f => {
    const el = document.getElementById(`el-${f}`);
    if (el) body[f] = el.value.trim();
  });

  const btn = document.querySelector("#edit-links-modal .btn-primary");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  try {
    const res  = await fetch(`/admin/api/destinations/${destId}/files`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const json = await res.json();
    if (json.success) {
      const dest = TMH_DATA.all_destinations.find(d => d.id === destId);
      if (dest) Object.assign(dest.files, body);
      closeEditLinks();
      showToast("✅ Links saved successfully.");
    } else {
      showToast(json.error || "Save failed — please try again.", true);
    }
  } catch(e) {
    showToast("Network error — links not saved.", true);
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

// ─── Tab switching ────────────────────────────────────────

function switchTab(name) {
  ["customers","destinations","settings"].forEach(tab => {
    document.getElementById(`tab-${tab}`)?.classList.toggle("tab-btn--active", tab === name);
    document.getElementById(`panel-${tab}`)?.classList.toggle("tab-panel--active", tab === name);
  });
}

// ─── Utility ─────────────────────────────────────────────

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
