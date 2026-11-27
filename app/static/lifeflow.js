import { announce, api, button, closeEditor, el, field } from "./ui.js";
import { finance, goals, overview, tasks } from "./views.js";

const main = document.querySelector("main");
const nav = document.querySelector(".nav");
const accountBox = document.querySelector("#account");
const notices = document.querySelector("#notice");
const routes = { overview, tasks, goals, finance };
const titles = { overview: "Обзор", tasks: "Задачи", goals: "Цели", finance: "Финансы" };
let account = null;
let demoAvailable = false;
let generation = 0;

function signIn(register = false) {
  generation += 1;
  closeEditor();
  nav.hidden = true;
  accountBox.replaceChildren();
  main.setAttribute("aria-busy", "false");
  document.title = register ? "Регистрация — LifeFlow" : "Вход — LifeFlow";

  const form = el("form", { class: "access-form" },
    field("Email", "email", { type: "email", required: true, autocomplete: "email", maxlength: 254 }),
    field("Пароль", "password", {
      type: "password", required: true, autocomplete: register ? "new-password" : "current-password",
      maxlength: 128, minlength: register ? 15 : 1,
    }));
  const error = el("p", { class: "form-error", role: "alert", hidden: true });
  const submit = el("button", { type: "submit", class: "button primary" }, register ? "Создать аккаунт" : "Войти");
  const toggle = button(register ? "Уже есть аккаунт? Войти" : "Создать аккаунт", () => {
    signIn(!register);
    main.querySelector("input").focus();
  }, "text-button accent-link");
  const demo = demoAvailable && button("Посмотреть демо →", async control => {
    control.disabled = true;
    submit.disabled = true;
    error.hidden = true;
    try {
      signedIn(await api("/auth/demo", "POST"));
    } catch (problem) {
      error.textContent = problem.message;
      error.hidden = false;
    } finally {
      control.disabled = false;
      submit.disabled = false;
    }
  });

  form.append(error, submit);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    error.hidden = true;
    submit.disabled = true;
    if (demo) demo.disabled = true;
    try {
      const data = Object.fromEntries(new FormData(form));
      signedIn(await api(register ? "/auth/register" : "/auth/login", "POST", data));
    } catch (problem) {
      error.textContent = problem.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
      if (demo) demo.disabled = false;
    }
  });

  main.replaceChildren(el("div", { class: "access-grid" },
    el("section", { class: "welcome" },
      el("div", { class: "orange-rule", "aria-hidden": "true" }),
      el("h1", {}, "Задачи, цели и финансы"),
      el("p", {}, "Планируйте дела, отслеживайте прогресс и ведите учёт в четырёх валютах.")),
    el("section", { class: "feature-card access-card" },
      el("h2", {}, register ? "Регистрация" : "Вход"),
      register && el("p", { class: "muted" }, "Используйте пароль из 15 символов или больше."),
      form, toggle, demo && el("div", { class: "demo-action" }, demo))));
}

function signedIn(user) {
  account = user;
  history.replaceState(null, "", "#overview");
  render(true);
}

function showAccount() {
  nav.hidden = false;
  accountBox.replaceChildren(
    el("span", { class: account.demo ? "demo-label" : "account-email" }, account.demo ? "Демоданные" : account.email),
    button("Выйти", async control => {
      control.disabled = true;
      try {
        await api("/auth/logout", "POST");
        account = null;
        history.replaceState(null, "", location.pathname);
        notices.hidden = true;
        signIn();
        main.querySelector("input").focus();
      } catch (problem) {
        announce(problem.message);
        control.disabled = false;
      }
    }, "button small"));
}

async function render(moveFocus = false) {
  if (!account) return;
  const requestId = ++generation;
  const [route, action] = location.hash.slice(1).split("/");
  const page = Object.hasOwn(routes, route) ? route : "overview";
  if (!accountBox.childElementCount) showAccount();
  document.title = `${titles[page]} — LifeFlow`;
  for (const link of nav.querySelectorAll("a")) {
    if (link.dataset.page === page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  main.setAttribute("aria-busy", "true");
  if (moveFocus) main.replaceChildren(el("p", { class: "loading", role: "status" }, "Загружаем раздел…"));
  try {
    const content = await routes[page](() => render(), action === "new");
    if (requestId !== generation) return;
    main.replaceChildren(...content);
    if (moveFocus && !document.querySelector("dialog[open]")) main.focus();
  } catch (problem) {
    if (requestId !== generation) return;
    main.replaceChildren(el("section", { class: "feature-card empty" },
      el("h1", {}, "Раздел не загрузился"), el("p", { role: "alert" }, problem.message),
      button("Попробовать ещё раз", () => render(true))));
  } finally {
    if (requestId === generation) main.setAttribute("aria-busy", "false");
  }
}

window.addEventListener("hashchange", () => {
  if (location.hash === "#content") return;
  closeEditor();
  render(true);
});
window.addEventListener("session-expired", () => {
  account = null;
  signIn();
  announce("Сессия закончилась. Войдите снова.");
});
document.querySelector(".skip").addEventListener("click", event => {
  event.preventDefault();
  main.focus();
});

try {
  const options = await api("/app/config");
  demoAvailable = options.demo_available;
  account = await api("/auth/me");
  await render();
} catch (problem) {
  signIn();
  if (problem.status !== 401) announce(problem.message);
}
