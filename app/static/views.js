import { allRows, amount, announce, api, button, closeEditor, dateLabel, editDialog, el, field, pageHeading, today } from "./ui.js";

const statuses = [["todo", "К выполнению"], ["in_progress", "В работе"], ["done", "Готово"]];
const currencies = [["RUB", "Рубли · RUB"], ["USD", "Доллары · USD"], ["EUR", "Евро · EUR"], ["CNY", "Юани · CNY"]];
const kinds = [["expense", "Расход"], ["income", "Доход"]];

function sectionTitle(title, path, linkText) {
  return el("div", { class: "section-title" }, el("h2", {}, title),
    path && el("a", { href: path, class: "accent-link" }, linkText));
}

function taskProgress(goal) {
  return el("div", { class: "goal-progress" },
    el("div", { class: "goal-progress-label" },
      el("span", {}, `Выполнено ${goal.completed_tasks} из ${goal.tasks.length}`),
      el("strong", { class: "number" }, `${goal.progress}%`)),
    el("progress", { value: goal.progress, max: 100, "aria-label": `Прогресс цели «${goal.title}»` }));
}

export async function overview() {
  const data = await api("/dashboard");
  const heading = pageHeading("Обзор", "Задачи, цели и финансы в одном месте.",
    el("a", { class: "button primary", href: "#tasks/new" }, "Новая задача"),
    dateLabel(data.today, { weekday: "long", day: "numeric", month: "long" }));
  const total = Object.values(data.task_counts).reduce((sum, count) => sum + count, 0);
  const distribution = el("dl", { class: "distribution" }, ...statuses.map(([key, label]) => el("div", {},
    el("dt", {}, label), el("dd", { class: "number" }, String(data.task_counts[key])))));
  const tasksCard = el("section", { class: "feature-card task-summary" },
    sectionTitle("Задачи", "#tasks", "Открыть доску →"),
    el("div", { class: "task-total number" }, String(total)),
    distribution);
  const balances = el("dl", { class: "balances" }, ...data.finances.map(row => el("div", {},
    el("dt", {}, row.currency), el("dd", { class: "number" }, amount(row.balance)))));
  const balanceCard = el("section", { class: "feature-card balance-card" },
    sectionTitle("Остатки", "#finance", "Все операции →"), balances);

  const goals = el("section", { class: "overview-list" }, sectionTitle("Цели", "#goals", "Все цели →"),
    data.goals.length ? el("ul", { class: "summary-list" }, ...data.goals.map(goal => el("li", {},
      el("h3", {}, goal.title), taskProgress(goal)))) : el("p", { class: "muted" }, "Цели появятся после добавления связанных задач."));
  const upcoming = el("section", { class: "overview-list" }, sectionTitle("Ближайшие задачи", "#tasks", "К задачам →"),
    data.upcoming.length ? el("ul", { class: "summary-list" }, ...data.upcoming.map(task =>
      el("li", { class: "upcoming-row" }, el("span", {}, task.title),
        el("time", { datetime: task.due_date, class: "meta" }, dateLabel(task.due_date))))) :
      el("p", { class: "muted" }, "Пока нет открытых задач со сроком."));
  return [heading, el("div", { class: "overview-grid" }, tasksCard, balanceCard),
    el("div", { class: "overview-grid overview-details" }, goals, upcoming)];
}

function entryFields(item) {
  return [field("Название", "title", { required: true, maxlength: 200, value: item?.title }),
    field("Описание", "description", { multiline: true, value: item?.description }),
    field("Срок", "due_date", { type: "date", value: item?.due_date })];
}

function entryPayload(values) {
  return { title: values.get("title"), description: values.get("description") || null, due_date: values.get("due_date") || null };
}

function editTask(task, refresh) {
  editDialog({
    title: task ? "Редактировать задачу" : "Новая задача",
    fields: [...entryFields(task), field("Статус", "status", { options: statuses, value: task?.status || "todo" })],
    save: values => api(task ? `/tasks/${task.id}` : "/tasks", task ? "PUT" : "POST",
      { ...entryPayload(values), status: values.get("status") }),
    remove: task && (() => api(`/tasks/${task.id}`, "DELETE")),
    confirmText: "Удалить задачу?", saved: refresh,
  });
}

function taskCard(task, refresh) {
  const statusControl = el("select", { class: "compact-select", "aria-label": `Статус задачи «${task.title}»` },
    ...statuses.map(([value, label]) => el("option", { value }, label)));
  statusControl.value = task.status;
  statusControl.addEventListener("change", async () => {
    statusControl.disabled = true;
    try {
      await api(`/tasks/${task.id}/status`, "PATCH", { status: statusControl.value });
      announce("Статус обновлён");
      refresh();
    } catch (problem) {
      statusControl.value = task.status;
      announce(problem.message);
    } finally {
      statusControl.disabled = false;
    }
  });
  return el("li", { class: "task-card" },
    button(task.title, () => editTask(task, refresh), "card-title"),
    task.description && el("p", { class: "clamp muted" }, task.description),
    el("div", { class: "task-meta" }, el("span", { class: "meta" }, dateLabel(task.due_date)), statusControl));
}

export async function tasks(refresh, autoCreate) {
  const rows = await allRows("/tasks");
  if (autoCreate && location.hash === "#tasks/new") {
    history.replaceState(null, "", "#tasks");
    editTask(null, refresh);
  }
  const board = el("div", { class: "board" }, ...statuses.map(([key, label]) => {
    const column = rows.filter(task => task.status === key);
    return el("section", { class: "board-column" }, el("div", { class: "column-title" },
      el("h2", {}, label), el("span", { class: "number meta" }, String(column.length))),
      column.length ? el("ul", { class: "task-list" }, ...column.map(task => taskCard(task, refresh))) :
        el("p", { class: "column-empty muted" }, "Здесь пока пусто"));
  }));
  return [pageHeading("Задачи", "Планируйте дела и меняйте их статус на доске.",
    button("Новая задача", () => editTask(null, refresh), "button primary")), board];
}

async function editGoal(goal, refresh) {
  const rows = await allRows("/tasks");
  const linked = new Set(goal?.tasks.map(task => task.id) || []);
  const options = rows.filter(task => task.goal_id === null || task.goal_id === goal?.id);
  const choices = el("fieldset", { class: "task-picker" }, el("legend", {}, "Связанные задачи"));
  if (options.length) {
    choices.append(...options.map(task => el("label", {},
      el("input", { type: "checkbox", name: "task_ids", value: task.id, checked: linked.has(task.id) }),
      el("span", {}, task.title))));
  } else {
    const tasksLink = el("a", { href: "#tasks/new", class: "accent-link" }, "Создать задачу");
    tasksLink.addEventListener("click", closeEditor);
    choices.append(el("p", { class: "muted" }, "Для цели нужна хотя бы одна свободная задача."), tasksLink);
  }
  editDialog({
    title: goal ? "Редактировать цель" : "Новая цель", fields: [...entryFields(goal), choices],
    save: values => {
      const taskIds = values.getAll("task_ids").map(Number);
      if (!taskIds.length) throw new Error("Выберите хотя бы одну связанную задачу.");
      return api(goal ? `/goals/${goal.id}` : "/goals", goal ? "PUT" : "POST", { ...entryPayload(values), task_ids: taskIds });
    },
    remove: goal && (() => api(`/goals/${goal.id}`, "DELETE")),
    confirmText: "Удалить цель? Связанные задачи останутся на доске.", saved: refresh,
  });
}

function launchGoalEditor(goal, refresh) {
  return async control => {
    control.disabled = true;
    try {
      await editGoal(goal, refresh);
    } catch (problem) {
      announce(problem.message);
    } finally {
      control.disabled = false;
    }
  };
}

export async function goals(refresh) {
  const rows = await allRows("/goals");
  const cards = rows.map(goal => el("article", { class: "feature-card goal-card" },
    el("div", { class: "section-title" }, el("h2", {}, goal.title),
      button("Изменить", launchGoalEditor(goal, refresh), "text-button")),
    goal.description && el("p", { class: "muted" }, goal.description),
    el("p", { class: "meta" }, dateLabel(goal.due_date)), taskProgress(goal),
    el("ul", { class: "linked-list" }, ...goal.tasks.map(task => el("li", {},
      el("span", { class: "status-mark", "data-status": task.status, "aria-hidden": "true" }),
      el("span", {}, task.title), el("span", { class: "meta" }, statuses.find(([key]) => key === task.status)[1]))))));
  return [pageHeading("Цели", "Прогресс считается по выполненным связанным задачам.",
    button("Новая цель", launchGoalEditor(null, refresh), "button primary")),
  cards.length ? el("div", { class: "goals-grid" }, ...cards) :
    el("div", { class: "feature-card empty" }, el("h2", {}, "Пока нет целей"),
      el("p", {}, "Создайте цель и выберите задачи, которые помогут её выполнить."))];
}

const financeState = { start: today().slice(0, 7) + "-01", end: today(), currency: "", offset: 0 };

function editTransaction(record, refresh) {
  editDialog({
    title: record ? "Редактировать операцию" : "Новая операция",
    fields: [field("Тип", "kind", { options: kinds, value: record?.kind || "expense" }),
      el("div", { class: "fields-row" },
        field("Сумма", "amount", { value: record?.amount, inputmode: "decimal", pattern: "[0-9]+([.,][0-9]{1,2})?", required: true }),
        field("Валюта", "currency", { options: currencies, value: record?.currency || financeState.currency || "RUB" })),
      field("Категория", "category", { required: true, maxlength: 80, value: record?.category }),
      field("Дата", "occurred_on", { required: true, type: "date", value: record?.occurred_on || today() }),
      field("Комментарий", "comment", { multiline: true, maxlength: 2000, value: record?.comment })],
    save: values => api(record ? `/finance/transactions/${record.id}` : "/finance/transactions", record ? "PUT" : "POST", {
      ...Object.fromEntries(values), amount: values.get("amount").replace(",", "."), comment: values.get("comment") || null,
    }),
    remove: record && (() => api(`/finance/transactions/${record.id}`, "DELETE")),
    confirmText: "Удалить операцию? Остаток и итоги пересчитаются.", saved: refresh,
  });
}

async function showRates(panel) {
  try {
    const data = await api("/finance/rates");
    const quotes = Object.entries(data.rub_per_unit).map(([code, rate]) => {
      return el("div", {}, el("dt", {}, code), el("dd", { class: "number" }, amount(rate, 4)));
    });
    const source = data.provider === "mirror"
      ? ["https://www.cbr-xml-daily.ru/", "Курсы ЦБ РФ в XML и JSON, API"]
      : ["https://www.cbr.ru/currency_base/daily/", "Источник ↗"];
    panel.replaceChildren(sectionTitle("Курсы Банка России", ...source),
      el("p", { class: "meta" }, `Рублей за единицу · ${dateLabel(data.rate_date, { dateStyle: "medium" })}${data.stale ? " · сохранённая котировка" : ""}`),
      el("dl", { class: "rate-list" }, ...quotes));
  } catch (problem) {
    panel.replaceChildren(sectionTitle("Курсы Банка России", "https://www.cbr.ru/currency_base/daily/", "Источник ↗"),
      el("p", { class: "muted" }, problem.message));
  }
}

function financeFilters(refresh) {
  const form = el("form", { class: "finance-filters" },
    field("С", "start", { type: "date", required: true, value: financeState.start }),
    field("По", "end", { type: "date", required: true, value: financeState.end }),
    field("Валюта операций", "currency", { options: [["", "Все валюты"], ...currencies], value: financeState.currency }),
    el("button", { class: "button", type: "submit" }, "Применить"));
  form.elements.start.addEventListener("change", () => { form.elements.end.min = form.elements.start.value; });
  form.elements.end.min = financeState.start;
  form.addEventListener("submit", event => {
    event.preventDefault();
    Object.assign(financeState, Object.fromEntries(new FormData(form)), { offset: 0 });
    refresh();
  });
  return form;
}

function ledgerTable(rows, refresh) {
  const headings = ["Дата", "Категория", "Тип", "Сумма", "Действие"];
  const body = rows.map(record => {
    const income = record.kind === "income";
    return el("tr", { role: "row" },
      el("td", { role: "cell", class: "transaction-date" }, el("time", { datetime: record.occurred_on }, dateLabel(record.occurred_on))),
      el("td", { role: "cell", class: "transaction-category" }, el("strong", {}, record.category), record.comment && el("span", { class: "meta transaction-note" }, record.comment)),
      el("td", { role: "cell", class: "transaction-kind" }, income ? "Доход" : "Расход"),
      el("td", { role: "cell", class: "number transaction-amount" }, `${income ? "+" : "−"}${amount(record.amount)} ${record.currency}`),
      el("td", { role: "cell", class: "transaction-action" }, button("Изменить", () => editTransaction(record, refresh), "text-button")));
  });
  const header = el("tr", { role: "row" }, ...headings.map(label => el("th", { role: "columnheader", scope: "col" }, label)));
  return el("div", { class: "table-wrap" }, el("table", { role: "table", "aria-label": "Финансовые операции" },
    el("thead", { role: "rowgroup" }, header), el("tbody", { role: "rowgroup" }, ...body)));
}

export async function finance(refresh) {
  const period = new URLSearchParams({ start: financeState.start, end: financeState.end });
  const query = new URLSearchParams(period);
  query.set("limit", "21");
  query.set("offset", financeState.offset);
  if (financeState.currency) query.set("currency", financeState.currency);
  const [totals, page] = await Promise.all([api(`/finance/summary?${period}`), api(`/finance/transactions?${query}`)]);
  if (!page.length && financeState.offset > 0) {
    financeState.offset = Math.max(0, financeState.offset - 20);
    return finance(refresh);
  }
  const cards = totals.map(row => {
    const figures = [["Доходы", row.income], ["Расходы", row.expense], ["Итог", row.net]];
    const totalsList = figures.map(([label, value]) =>
      el("div", {}, el("dt", {}, label), el("dd", { class: "number" }, amount(value))));
    return el("section", { class: "feature-card currency-card" },
      el("h2", {}, row.currency), el("p", { class: "balance-value number" }, amount(row.balance)),
      el("p", { class: "meta" }, "Остаток за всё время"),
      el("dl", { class: "currency-totals" }, ...totalsList));
  });
  const rates = el("section", { class: "feature-card rates" }, el("p", { class: "muted", role: "status" }, "Загружаем курсы Банка России…"));
  showRates(rates);
  const pagination = el("div", { class: "pagination" },
    financeState.offset > 0 && button("← Назад", () => { financeState.offset -= 20; refresh(); }),
    page.length > 20 && button("Далее →", () => { financeState.offset += 20; refresh(); }));
  return [pageHeading("Финансы", "Доходы, расходы и остатки отдельно по каждой валюте.",
    button("Новая операция", () => editTransaction(null, refresh), "button primary")),
  financeFilters(refresh), el("div", { class: "currency-grid" }, ...cards), rates,
  el("section", { class: "ledger" }, sectionTitle("Операции"), page.length ? ledgerTable(page.slice(0, 20), refresh) :
    el("p", { class: "muted" }, "За выбранный период нет операций."), pagination)];
}
