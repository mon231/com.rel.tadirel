"use strict";

const state = {
  known: [],
  scanResults: new Map(), // mac -> device
  scanning: false,
  currentDetailMac: null,
  caps: null,
};

const el = (id) => document.getElementById(id);

function toast(message, isError) {
  const t = el("toast");
  t.textContent = message;
  t.hidden = false;
  t.className = "toast" + (isError ? " error" : "");
  clearTimeout(t._hideTimer);
  t._hideTimer = setTimeout(() => (t.hidden = true), 3200);
}

async function call(fn, ...args) {
  try {
    return await eel[fn](...args)();
  } catch (err) {
    toast(String(err && err.errorText ? err.errorText : err), true);
    throw err;
  }
}

/* ---------------------------------------------------------- known devices */

async function loadKnown() {
  const devices = await call("list_known_devices");
  state.known = devices;
  renderKnown();
}

function renderKnown() {
  const list = el("known-list");
  list.innerHTML = "";
  if (state.known.length === 0) {
    list.innerHTML =
      '<li class="empty-hint">No saved air conditioners yet. Scan your network below and name one to save it.</li>';
    return;
  }
  for (const d of state.known) {
    const li = document.createElement("li");
    li.className = "device-row" + (d.reachable ? "" : " unreachable");
    li.innerHTML = `
      <span class="device-dot"></span>
      <span class="device-info">
        <div class="device-name">${escapeHtml(d.name)}</div>
        <div class="device-meta">${formatMac(d.mac)}${d.ip ? " &middot; " + d.ip : ""}${
      d.reachable ? "" : " &middot; unreachable"
    }</div>
      </span>
      <button class="icon-btn danger trash-btn" title="Remove">&#128465;</button>
    `;
    if (d.reachable) {
      li.addEventListener("click", (ev) => {
        if (ev.target.closest(".trash-btn")) return;
        openDetail(d.mac);
      });
    }
    li.querySelector(".trash-btn").addEventListener("click", async (ev) => {
      ev.stopPropagation();
      if (!confirm(`Remove "${d.name}" from saved devices?`)) return;
      await call("remove_device", d.mac);
      toast(`Removed "${d.name}"`);
      await loadKnown();
    });
    list.appendChild(li);
  }
}

/* ------------------------------------------------------------------ scan */

async function startScan() {
  if (state.scanning) return;
  state.scanning = true;
  state.scanResults = new Map();
  renderScan();

  el("scan-btn").disabled = true;
  el("scan-progress").hidden = false;
  const startedAt = Date.now();
  const TOTAL_MS = 12000;

  const { scan_id } = await call("start_scan");

  const tick = async () => {
    const elapsedMs = Date.now() - startedAt;
    const pct = Math.min(100, (elapsedMs / TOTAL_MS) * 100);
    el("scan-progress-fill").style.width = pct + "%";
    el("scan-progress-label").textContent = `Scanning… ${Math.min(
      12,
      Math.round(elapsedMs / 1000)
    )}s / 12s`;

    const res = await call("poll_scan", scan_id);
    for (const d of res.new) {
      state.scanResults.set(d.mac, d);
    }
    renderScan();

    if (res.done) {
      state.scanning = false;
      el("scan-btn").disabled = false;
      el("scan-progress-label").textContent = `Done &mdash; found ${state.scanResults.size} unit(s)`;
      setTimeout(() => (el("scan-progress").hidden = true), 1500);
      return;
    }
    setTimeout(tick, 350);
  };
  tick();
}

function renderScan() {
  const list = el("scan-list");
  list.innerHTML = "";
  if (state.scanResults.size === 0) {
    if (!state.scanning) {
      list.innerHTML = '<li class="empty-hint">No scan run yet.</li>';
    }
    return;
  }
  for (const d of state.scanResults.values()) {
    const li = document.createElement("li");
    li.className = "device-row";
    const nameBlock = d.paired
      ? `<div class="device-name">${escapeHtml(d.name)} <span class="device-meta">(saved)</span></div>`
      : `<div class="device-name">Unnamed unit</div>`;
    li.innerHTML = `
      <span class="device-dot"></span>
      <span class="device-info">
        ${nameBlock}
        <div class="device-meta">${formatMac(d.mac)} &middot; ${d.ip}</div>
      </span>
    `;
    if (!d.paired) {
      const btn = document.createElement("button");
      btn.className = "name-btn";
      btn.textContent = "Pair";
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const name = prompt("Name for this air conditioner:");
        if (!name) return;
        await call("set_device_name", d.mac, d.ip, d.mid, name);
        d.paired = true;
        d.name = name;
        toast(`Saved "${name}"`);
        renderScan();
        await loadKnown();
      });
      li.appendChild(btn);
    } else {
      li.addEventListener("click", () => openDetail(d.mac));
    }
    list.appendChild(li);
  }
}

/* --------------------------------------------------------------- detail */

async function openDetail(mac) {
  showLoading();
  try {
    if (!state.caps) state.caps = await call("capabilities");
    let data;
    try {
      data = await call("get_status", mac);
    } catch (err) {
      return;
    }
    state.currentDetailMac = mac;

    const known = state.known.find((d) => d.mac === mac) || { name: mac };
    el("detail-name").textContent = known.name;
    el("detail-sub").textContent = `${formatMac(mac)} · ${data.ip}`;

    renderControls(data.status);
    el("detail-backdrop").hidden = false;
  } finally {
    hideLoading();
  }
}

function showLoading() {
  el("loading-overlay").hidden = false;
}

function hideLoading() {
  el("loading-overlay").hidden = true;
}

function closeDetail() {
  el("detail-backdrop").hidden = true;
  state.currentDetailMac = null;
}

function renderControls(status) {
  const root = el("detail-controls");
  root.innerHTML = "";

  for (const spec of state.caps.controls) {
    root.appendChild(buildControlRow(spec, status[spec.key]));
  }
  for (const spec of state.caps.readonly) {
    const row = document.createElement("div");
    row.className = "control-row";
    row.innerHTML = `<div class="control-label"><span>${spec.label}</span>
      <span class="control-value">${formatReadonly(status[spec.key])}</span></div>`;
    root.appendChild(row);
  }
}

function formatReadonly(value) {
  if (value === null || value === undefined) return "—";
  return value + "°C";
}

function buildControlRow(spec, value) {
  const row = document.createElement("div");
  row.className = "control-row";

  if (spec.kind === "toggle") {
    const checked = !!value;
    row.innerHTML = `
      <div class="control-label">
        <span>${spec.label}</span>
        <label class="switch">
          <input type="checkbox" ${checked ? "checked" : ""} />
          <span class="slider"></span>
        </label>
      </div>`;
    row.querySelector("input").addEventListener("change", (ev) => {
      sendChange({ [spec.key]: ev.target.checked ? 1 : 0 });
    });
    return row;
  }

  if (spec.kind === "enum") {
    row.innerHTML = `<div class="control-label"><span>${spec.label}</span></div>
      <div class="chip-row"></div>`;
    const chipRow = row.querySelector(".chip-row");
    for (const choice of spec.choices) {
      const chip = document.createElement("button");
      chip.className = "chip" + (choice.value === value ? " active" : "");
      chip.textContent = choice.label;
      chip.addEventListener("click", () => sendChange({ [spec.key]: choice.value }));
      chipRow.appendChild(chip);
    }
    return row;
  }

  if (spec.kind === "int_range") {
    const current = value ?? spec.min ?? 20;
    row.innerHTML = `
      <div class="control-label"><span>${spec.label}</span></div>
      <div class="stepper">
        <button class="dec">&minus;</button>
        <span class="temp-value">${current}°C</span>
        <button class="inc">&plus;</button>
      </div>`;
    const valueEl = row.querySelector(".temp-value");
    row.querySelector(".dec").addEventListener("click", () => {
      const next = Math.max(spec.min, current - 1);
      sendChange({ [spec.key]: next });
    });
    row.querySelector(".inc").addEventListener("click", () => {
      const next = Math.min(spec.max, current + 1);
      sendChange({ [spec.key]: next });
    });
    return row;
  }

  row.textContent = `${spec.label}: ${value}`;
  return row;
}

async function sendChange(changes) {
  const mac = state.currentDetailMac;
  if (!mac) return;
  setControlsBusy(true);
  try {
    // send_command blocks until the AC's own status confirms the change
    // (or a ~7s confirm timeout elapses) -- not just that a packet went out.
    const result = await call("send_command", mac, changes);
    renderControls(result.status);
    if (!result.confirmed) {
      toast("Sent, but the AC hasn't confirmed the change yet — showing its latest real status.", true);
    }
  } catch (err) {
    // toast already shown by call()
  } finally {
    setControlsBusy(false);
  }
}

function setControlsBusy(busy) {
  const root = el("detail-controls");
  root.classList.toggle("busy", busy);
  root.querySelectorAll("input, button").forEach((elm) => (elm.disabled = busy));
}

/* ------------------------------------------------------------------ util */

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function formatMac(mac) {
  return mac.match(/.{1,2}/g).join(":").toUpperCase();
}

/* ------------------------------------------------------------------ wire */

el("refresh-known-btn").addEventListener("click", loadKnown);
el("scan-btn").addEventListener("click", startScan);
el("detail-close-btn").addEventListener("click", closeDetail);
el("detail-rename-btn").addEventListener("click", async () => {
  const mac = state.currentDetailMac;
  if (!mac) return;
  const current = state.known.find((d) => d.mac === mac);
  const name = prompt("New name:", current ? current.name : "");
  if (!name) return;
  await call("rename_device", mac, name);
  el("detail-name").textContent = name;
  await loadKnown();
});
el("detail-backdrop").addEventListener("click", (ev) => {
  if (ev.target === el("detail-backdrop")) closeDetail();
});

loadKnown();
