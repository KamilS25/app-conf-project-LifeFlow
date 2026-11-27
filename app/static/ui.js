const dialog = document.querySelector("#editor");
const notice = document.querySelector("#notice");
let noticeTimer;
let nextFieldId = 0;

export async function api(path, method = "GET", data) {
  const headers = { Accept: "application/json", "X-LifeFlow-Request": "1" };
  if (data !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(path, { method, headers, body: JSON.stringify(data), credentials: "same-origin" });
  } catch {
    throw new Error("Нет связи с LifeFlow. Проверьте подключение и повторите попытку.");
  }
  if (response.status === 204) return null;
  const result = await response.json();
  if (response.ok) return result;

  if (response.status === 401 && !path.startsWith("/auth/")) {
    window.dispatchEvent(new Event("session-expired"));
  }
  const validation = path.startsWith("/auth/")
    ? "Проверьте email и пароль. Для регистрации нужно не меньше 15 символов."
    : "Проверьте обязательные поля и формат введённых значений.";
  const missing = result.detail === "Task not found" ? "Задача не найдена" : result.detail;
  const error = new Error(typeof missing === "string" ? missing : validation);
  error.status = response.status;
  throw error;
}

export async function allRows(path) {
  const rows = [];
  const separator = path.includes("?") ? "&" : "?";
  for (let offset = 0; ; offset += 100) {
    const page = await api(`${path}${separator}offset=${offset}&limit=100`);
    rows.push(...page);
    if (page.length < 100) return rows;
  }
}

export function el(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value === true) element.setAttribute(name, "");
    else if (value !== false && value != null) element.setAttribute(name, value);
  }
  element.append(...children.filter(child => child != null && child !== false));
  return element;
}

export function button(text, action, className = "button") {
  const control = el("button", { type: "button", class: className }, text);
  control.addEventListener("click", () => action(control));
  return control;
}

export function pageHeading(title, description, action, context) {
  return el("div", { class: "page-heading" }, el("div", {},
    context && el("p", { class: "page-context" }, context),
    el("h1", {}, title), el("p", { class: "page-description" }, description)), action);
}

export function field(label, name, { value, options, multiline, ...attrs } = {}) {
  const id = `input-${++nextFieldId}`;
  const controlAttrs = { id, name, ...attrs };
  let control;
  if (options) {
    control = el("select", controlAttrs, ...options.map(([key, text]) => el("option", { value: key }, text)));
  } else if (multiline) {
    control = el("textarea", { rows: 3, ...controlAttrs });
  } else {
    control = el("input", controlAttrs);
  }
  if (value != null) control.value = value;
  return el("div", { class: "field" }, el("label", { for: id }, label), control);
}

export function dateLabel(value, options = { day: "numeric", month: "short" }) {
  if (!value) return "Без срока";
  return new Intl.DateTimeFormat("ru-RU", options).format(new Date(`${value}T00:00:00`));
}

export function today() {
  const now = new Date();
  return [now.getFullYear(), now.getMonth() + 1, now.getDate()].map(part => String(part).padStart(2, "0")).join("-");
}

export function amount(value, digits = 2) {
  const [integer, fraction = ""] = String(value).split(".");
  const absoluteInteger = integer.replace(/^-/, "");
  const magnitude = new Intl.NumberFormat("ru-RU").format(BigInt(absoluteInteger));
  return `${integer.startsWith("-") ? "−" : ""}${magnitude},${fraction.padEnd(digits, "0")}`;
}

export function announce(text) {
  clearTimeout(noticeTimer);
  notice.textContent = text;
  notice.hidden = false;
  noticeTimer = setTimeout(() => { notice.hidden = true; }, 5000);
}

export function closeEditor() {
  if (dialog.open) dialog.close();
}

export function editDialog({ title, fields, save, remove, confirmText, saved }) {
  const form = el("form", { class: "editor-form" });
  const error = el("p", { class: "form-error", role: "alert", hidden: true });
  const confirmation = el("p", { class: "form-error", role: "status", hidden: true });
  const submit = el("button", { class: "button primary", type: "submit" }, "Сохранить");
  const cancel = button("Отмена", closeEditor);
  let removeButton;

  function showError(problem) {
    error.textContent = problem.message;
    error.hidden = false;
  }

  if (remove) {
    removeButton = button("Удалить", async control => {
      if (confirmation.hidden) {
        confirmation.textContent = confirmText;
        confirmation.hidden = false;
        control.textContent = "Подтвердить удаление";
        return;
      }
      control.disabled = true;
      submit.disabled = true;
      try {
        await remove();
        closeEditor();
        announce("Запись удалена");
        saved();
      } catch (problem) {
        showError(problem);
      } finally {
        control.disabled = false;
        submit.disabled = false;
      }
    }, "text-button danger");
  }

  form.append(...fields, error, confirmation,
    el("div", { class: "dialog-actions" }, removeButton, el("div", { class: "button-row" }, cancel, submit)));
  form.addEventListener("submit", async event => {
    event.preventDefault();
    error.hidden = true;
    submit.disabled = true;
    if (removeButton) removeButton.disabled = true;
    try {
      await save(new FormData(form));
      closeEditor();
      announce("Изменения сохранены");
      saved();
    } catch (problem) {
      showError(problem);
    } finally {
      submit.disabled = false;
      if (removeButton) removeButton.disabled = false;
    }
  });
  dialog.replaceChildren(el("h2", { id: "editor-title" }, title), form);
  if (!dialog.open) dialog.showModal();
}
