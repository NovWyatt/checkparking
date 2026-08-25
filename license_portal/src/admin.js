import {
  fluentBadge,
  fluentButton,
  fluentOption,
  fluentSelect,
  fluentTextArea,
  fluentTextField,
  provideFluentDesignSystem,
} from "@fluentui/web-components";

import "./admin.css";

provideFluentDesignSystem().register(
  fluentBadge(),
  fluentButton(),
  fluentOption(),
  fluentSelect(),
  fluentTextArea(),
  fluentTextField(),
);

const app = document.querySelector("#app");
const state = { licenses: [], busy: false };

function element(name, attributes = {}, children = []) {
  const node = document.createElement(name);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

function showLogin(message = "") {
  app.replaceChildren();
  const feedback = element("p", { class: `feedback ${message ? "is-error" : ""}`, text: message || "Chỉ quản trị viên được cấp mã mới có thể quản lý key." });
  const form = element("form", { class: "login-card", onsubmit: onLogin });
  form.append(
    element("div", { class: "brand-mark", text: "CV" }),
    element("p", { class: "eyebrow", text: "Check Vehicle OCR" }),
    element("h1", { text: "Quản trị bản quyền" }),
    element("p", { class: "login-copy", text: "Đăng nhập bằng mã quản trị bí mật để cấp, thu hồi và đặt lại thiết bị." }),
    element("label", { class: "field-label", for: "admin-code", text: "Mã quản trị" }),
    element("fluent-text-field", { id: "admin-code", name: "code", type: "password", autocomplete: "current-password", required: "", "aria-describedby": "login-help" }),
    element("p", { id: "login-help", class: "field-help", text: "Mã không được lưu trong trình duyệt hoặc trang quản trị." }),
    element("fluent-button", { appearance: "accent", type: "submit", class: "full-button", text: "Đăng nhập" }),
    feedback,
  );
  app.append(form);
  form.querySelector("#admin-code").focus();
}

async function onLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const codeControl = formControl(form, "code");
  const code = codeControl.value;
  setBusy(form, true);
  try {
    await api("/api/admin/login", { method: "POST", body: { code } });
    codeControl.value = "";
    await showDashboard();
  } catch (error) {
    showLogin(messageFrom(error));
  }
}

async function showDashboard() {
  app.replaceChildren();
  const shell = element("section", { class: "dashboard-shell" });
  const header = element("header", { class: "dashboard-header" });
  header.append(
    element("div", {}, [element("p", { class: "eyebrow", text: "Check Vehicle OCR" }), element("h1", { text: "Bản quyền" }), element("p", { class: "header-copy", text: "Cấp key, theo dõi thiết bị và thu hồi quyền dùng ứng dụng." })]),
    element("div", { class: "header-actions" }, [
      element("fluent-button", { appearance: "outline", onclick: refreshLicenses, text: "Làm mới" }),
      element("fluent-button", { appearance: "stealth", onclick: logout, text: "Đăng xuất" }),
    ]),
  );
  const issuePanel = buildIssuePanel();
  const overview = buildOverview();
  const listPanel = buildListPanel();
  shell.append(header, overview, issuePanel, listPanel);
  app.append(shell);
  await refreshLicenses();
}

function buildOverview() {
  const section = element("section", { class: "overview", "aria-label": "Tổng quan bản quyền" });
  section.append(
    metric("active-count", "Đang hoạt động", "0"),
    metric("time-count", "Có thời hạn", "0"),
    metric("perpetual-count", "Vĩnh viễn", "0"),
  );
  return section;
}

function metric(id, label, value) {
  return element("div", { class: "metric" }, [element("span", { class: "metric-value", id, text: value }), element("span", { class: "metric-label", text: label })]);
}

function buildIssuePanel() {
  const section = element("section", { class: "panel issue-panel" });
  const form = element("form", { class: "issue-form", onsubmit: issueLicense });
  form.append(
    element("div", { class: "panel-heading" }, [element("h2", { text: "Cấp key mới" }), element("p", { text: "Key chỉ hiển thị một lần sau khi tạo. Hãy sao chép và gửi cho người dùng ngay." })]),
    field("Loại key", "licenseType", select("licenseType", [["time", "Có thời hạn"], ["perpetual", "Vĩnh viễn"]])),
    field("Ngày hết hạn", "expiresAt", element("input", { type: "date", name: "expiresAt", required: "" })),
    field("Số thiết bị", "maxDevices", element("input", { type: "number", name: "maxDevices", min: "1", max: "10", value: "1", required: "" })),
    field("Ghi chú", "note", element("textarea", { name: "note", rows: "2", maxlength: "240", placeholder: "Ví dụ: Công ty Minh Phát" })),
    element("div", { class: "issue-actions" }, [element("fluent-button", { appearance: "accent", type: "submit", text: "Tạo key" }), element("p", { class: "inline-status", id: "issue-status", text: "" })]),
  );
  formControl(form, "licenseType").addEventListener("change", () => syncExpiryControl(form));
  section.append(form);
  return section;
}

function field(label, name, control) {
  const wrapper = element("label", { class: "form-field" });
  wrapper.append(element("span", { text: label }), control);
  if (name && !control.getAttribute("name")) control.setAttribute("name", name);
  return wrapper;
}

function select(name, options) {
  const control = element("fluent-select", { name });
  for (const [value, label] of options) control.append(element("fluent-option", { value, text: label }));
  return control;
}

function formControl(form, name) {
  const control = form.querySelector(`[name="${name}"]`);
  if (!control) throw new Error(`Không tìm thấy trường biểu mẫu: ${name}`);
  return control;
}

function syncExpiryControl(form) {
  const isPerpetual = formControl(form, "licenseType").value === "perpetual";
  const expiresAt = formControl(form, "expiresAt");
  expiresAt.disabled = isPerpetual;
  expiresAt.required = !isPerpetual;
  if (isPerpetual) expiresAt.value = "";
}

function buildListPanel() {
  const section = element("section", { class: "panel list-panel" });
  section.append(
    element("div", { class: "panel-heading list-heading" }, [
      element("div", {}, [element("h2", { text: "Danh sách key" }), element("p", { id: "list-summary", text: "Đang tải danh sách key." })]),
      element("span", { id: "load-state", class: "load-state", text: "" }),
    ]),
    element("div", { class: "table-wrap" }, [element("table", { class: "licenses-table" }, [
      element("thead", {}, [element("tr", {}, ["Trạng thái", "Loại", "Hết hạn", "Thiết bị", "Ghi chú", "Thao tác"].map((text) => element("th", { text, scope: "col" })))]),
      element("tbody", { id: "licenses-body" }),
    ])]),
  );
  return section;
}

async function refreshLicenses() {
  const loading = document.querySelector("#load-state");
  if (loading) loading.textContent = "Đang tải…";
  try {
    const result = await api("/api/admin/licenses");
    state.licenses = result.licenses || [];
    renderLicenses();
  } catch (error) {
    if (error.status === 401) return showLogin("Phiên quản trị đã hết hạn. Hãy đăng nhập lại.");
    if (loading) loading.textContent = messageFrom(error);
  }
}

function renderLicenses() {
  const body = document.querySelector("#licenses-body");
  const summary = document.querySelector("#list-summary");
  if (!body || !summary) return;
  body.replaceChildren();
  const active = state.licenses.filter((license) => license.status === "active");
  setText("#active-count", String(active.length));
  setText("#time-count", String(active.filter((license) => license.license_type === "time").length));
  setText("#perpetual-count", String(active.filter((license) => license.license_type === "perpetual").length));
  summary.textContent = state.licenses.length ? `${state.licenses.length} key được quản lý` : "Chưa có key nào.";
  setText("#load-state", "");
  if (!state.licenses.length) {
    const cell = element("td", { colspan: "6", class: "empty-row", text: "Chưa có key. Tạo key đầu tiên ở biểu mẫu phía trên." });
    body.append(element("tr", {}, [cell]));
    return;
  }
  for (const license of state.licenses) {
    const row = element("tr");
    row.append(
      tableCell(statusBadge(license)),
      tableCell(license.license_type === "perpetual" ? "Vĩnh viễn" : "Có thời hạn"),
      tableCell(license.expires_at ? formatDate(license.expires_at) : "Không hết hạn"),
      tableCell(`${license.active_devices}/${license.max_devices}`),
      tableCell(license.note || "-"),
      actionCell(license),
    );
    body.append(row);
  }
}

function statusBadge(license) {
  const badge = element("fluent-badge", { appearance: license.status === "active" ? "accent" : "neutral", text: license.status === "active" ? "Đang hoạt động" : "Đã thu hồi" });
  return badge;
}

function tableCell(content) {
  const cell = element("td");
  if (typeof content === "string") cell.textContent = content;
  else cell.append(content);
  return cell;
}

function actionCell(license) {
  const cell = element("td", { class: "actions-cell" });
  if (license.status === "active") cell.append(element("fluent-button", { appearance: "outline", onclick: () => revoke(license), text: "Thu hồi" }));
  cell.append(element("fluent-button", { appearance: "stealth", onclick: () => resetDevices(license), text: "Đặt lại máy" }));
  return cell;
}

async function issueLicense(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = form.querySelector("#issue-status");
  setBusy(form, true);
  status.textContent = "Đang tạo key…";
  try {
    const licenseType = formControl(form, "licenseType");
    const expiresAt = formControl(form, "expiresAt");
    const maxDevices = formControl(form, "maxDevices");
    const note = formControl(form, "note");
    const result = await api("/api/admin/licenses", {
      method: "POST",
      body: {
        licenseType: licenseType.value,
        expiresAt: expiresAt.value,
        maxDevices: maxDevices.value,
        note: note.value,
      },
    });
    form.reset();
    licenseType.value = "time";
    expiresAt.value = "";
    maxDevices.value = "1";
    note.value = "";
    syncExpiryControl(form);
    status.textContent = "Đã tạo key.";
    showIssuedKey(result.key);
    await refreshLicenses();
  } catch (error) {
    status.textContent = messageFrom(error);
  } finally {
    setBusy(form, false);
  }
}

async function revoke(license) {
  if (!confirm("Thu hồi key này? Ứng dụng đã kích hoạt sẽ bị khóa khi đến lần kiểm tra bản quyền tiếp theo.")) return;
  await mutate(`/api/admin/licenses/${license.id}/revoke`, "Đã thu hồi key.");
}

async function resetDevices(license) {
  if (!confirm("Đặt lại toàn bộ thiết bị của key này? Người dùng sẽ cần kích hoạt lại key.")) return;
  await mutate(`/api/admin/licenses/${license.id}/reset-devices`, "Đã đặt lại thiết bị.");
}

async function mutate(path, successMessage) {
  try {
    await api(path, { method: "POST", body: {} });
    await refreshLicenses();
    setText("#load-state", successMessage);
  } catch (error) {
    if (error.status === 401) return showLogin("Phiên quản trị đã hết hạn. Hãy đăng nhập lại.");
    setText("#load-state", messageFrom(error));
  }
}

async function logout() {
  try {
    await api("/api/admin/logout", { method: "POST", body: {} });
  } finally {
    showLogin("Đã đăng xuất.");
  }
}

function showIssuedKey(key) {
  const overlay = element("div", { class: "key-dialog-backdrop", role: "presentation" });
  const dialog = element("section", { class: "key-dialog", role: "dialog", "aria-modal": "true", "aria-labelledby": "issued-key-title" });
  const code = element("code", { class: "issued-key", text: key });
  const copy = element("fluent-button", { appearance: "accent", text: "Sao chép key", onclick: async () => {
    await navigator.clipboard.writeText(key);
    copy.textContent = "Đã sao chép";
  } });
  dialog.append(
    element("p", { class: "eyebrow", text: "Key mới" }),
    element("h2", { id: "issued-key-title", text: "Sao chép key ngay" }),
    element("p", { text: "Vì lý do bảo mật, key gốc sẽ không xuất hiện lại trong danh sách quản trị." }),
    code,
    element("div", { class: "dialog-actions" }, [copy, element("fluent-button", { appearance: "outline", text: "Đã lưu key", onclick: () => overlay.remove() })]),
  );
  overlay.append(dialog);
  document.body.append(overlay);
  copy.focus();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  let payload = {};
  try { payload = await response.json(); } catch { /* API errors are normalized below. */ }
  if (!response.ok) {
    const error = new Error(payload.error || "Không thể hoàn tất yêu cầu.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

function setBusy(form, busy) {
  for (const control of form.querySelectorAll("fluent-button, fluent-text-field, fluent-select, input, textarea")) control.disabled = busy;
}

function setText(selector, value) {
  const node = document.querySelector(selector);
  if (node) node.textContent = value;
}

function messageFrom(error) {
  return error instanceof Error ? error.message : "Không thể hoàn tất yêu cầu.";
}

function formatDate(value) {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeZone: "Asia/Ho_Chi_Minh" }).format(new Date(value));
}

showLogin();
