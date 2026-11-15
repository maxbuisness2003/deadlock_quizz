/* Deadlock Quiz - client logic.
   The server owns the game state and never sends the right answer before
   the player has answered. */

const $ = (sel) => document.querySelector(sel);

const KIND_LABELS = {
  stat: "характеристика",
  upgrade: "прокачка",
  price: "цена в дюшах",
  tier: "тир магазина",
};

const LETTERS = ["A", "B", "C", "D", "E", "F"];
const RING_CIRC = 2 * Math.PI * 60;

const settings = { slot: "all", mode: "buttons", length: 15 };

let questionStartedAt = 0;
let timerHandle = null;
let submitting = false;
let lastScore = 0;

/* ------------------------------------------------------------- helpers */
/* Motion is opt-in: it follows the OS preference, but ?motion=on / off wins. */
(function setupMotion() {
  const override = new URLSearchParams(window.location.search).get("motion");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const enabled = override === "on" || (override !== "off" && !reduced);
  if (enabled) document.documentElement.classList.add("motion-on");
})();

/* Entrance animations end on the element's own style, so they can be dropped
   when they finish - that keeps the element painted by the static rules. */
const ENTRANCE_ANIMATIONS = new Set([
  "dropIn", "heroIn", "rise", "cardIn", "questionIn", "sheetIn",
]);

document.addEventListener("animationend", (event) => {
  if (!ENTRANCE_ANIMATIONS.has(event.animationName)) return;
  const target = event.target;
  if (target instanceof HTMLElement) target.style.animation = "none";
});

function showScreen(name) {
  ["home", "quiz", "result"].forEach((id) => {
    $(`#screen-${id}`).classList.toggle("active", id === name);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setupSegmented(id, onChange) {
  const group = $(`#${id}`);
  group.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    group.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    onChange(button.dataset.value);
  });
}

async function postJSON(url, body) {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({ error: "Сервер вернул неожиданный ответ" }));
    if (!response.ok && !data.error) data.error = `Ошибка ${response.status}`;
    return data;
  } catch (err) {
    return { error: "Нет связи с сервером. Попробуйте ещё раз." };
  }
}

/* ----------------------------------------------------------- animation */
function animateNumber(element, from, to, duration = 550) {
  if (from === to) {
    element.textContent = String(to);
    return;
  }
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    element.textContent = String(Math.round(from + (to - from) * eased));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* The answer buttons lean towards the cursor - a small, smooth tilt. */
function attachTilt(button) {
  button.addEventListener("pointermove", (event) => {
    if (button.disabled) return;
    const rect = button.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width;
    const py = (event.clientY - rect.top) / rect.height;
    button.style.setProperty("--mx", `${px * 100}%`);
    button.style.setProperty("--my", `${py * 100}%`);
    button.style.setProperty("--rx", `${(0.5 - py) * 5}deg`);
    button.style.setProperty("--ry", `${(px - 0.5) * 6}deg`);
  });
  button.addEventListener("pointerleave", () => {
    button.style.removeProperty("--mx");
    button.style.removeProperty("--my");
    button.style.removeProperty("--rx");
    button.style.removeProperty("--ry");
  });
}

function burstFrom(element, color) {
  const rect = element.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  for (let i = 0; i < 18; i += 1) {
    const particle = document.createElement("i");
    particle.className = "particle";
    const angle = (Math.PI * 2 * i) / 18 + (Math.random() - 0.5) * 0.5;
    const distance = 50 + Math.random() * 90;
    particle.style.left = `${cx}px`;
    particle.style.top = `${cy}px`;
    particle.style.setProperty("--dx", `${Math.cos(angle) * distance}px`);
    particle.style.setProperty("--dy", `${Math.sin(angle) * distance}px`);
    particle.style.background = i % 3 === 0 ? "#ffb545" : color;
    document.body.appendChild(particle);
    setTimeout(() => particle.remove(), 1000);
  }
}

function rankFor(accuracy, bestStreak) {
  if (accuracy >= 95) return "🏆 Легенда Deadlock";
  if (accuracy >= 80) return "🎯 Знаток предметов";
  if (accuracy >= 60) return "⚔️ Уверенный боец";
  if (accuracy >= 40) return "🔧 Ученик";
  if (bestStreak >= 3) return "⚡ Горячая серия";
  return "🌱 Новичок";
}

/* --------------------------------------------------------------- start */
async function startGame() {
  const button = $("#start-btn");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Загрузка…";
  try {
    const data = await postJSON("/api/start", settings);
    if (data.error) {
      window.alert(data.error);
      return;
    }
    lastScore = 0;
    showScreen("quiz");
    renderQuestion(data.question);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

/* ------------------------------------------------------------ question */
function renderQuestion(question) {
  if (!question) return;
  submitting = false;

  $("#q-index").textContent = question.index + 1;
  $("#q-total").textContent = question.total;
  $("#q-score").textContent = question.score;
  lastScore = question.score;
  updateStreak(question.streak);
  $("#q-kind").textContent = KIND_LABELS[question.kind] || "вопрос";
  $("#q-prompt").textContent = question.prompt;
  $("#q-item-name").textContent = question.item.name;

  const image = $("#q-image");
  image.classList.remove("ready");
  image.src = question.item.image || "";
  image.alt = question.item.name;
  if (image.complete && image.naturalWidth > 0) {
    image.classList.add("ready");
  } else {
    image.addEventListener("load", () => image.classList.add("ready"), { once: true });
  }
  if (question.preload) {
    const ahead = new Image();
    ahead.src = question.preload;
  }

  $("#q-feedback").innerHTML = "";
  $("#q-hint-text").textContent = "";
  $("#q-hint-btn").disabled = false;

  const badges = $("#q-badges");
  badges.innerHTML = "";
  const slot = document.createElement("span");
  slot.className = `badge slot-${question.item.slot}`;
  slot.textContent = question.item.slot_label;
  const tier = document.createElement("span");
  tier.className = "badge";
  tier.textContent = `${question.item.tier} тир`;
  badges.append(slot, tier);

  renderProgress(question.index, question.total);

  const answers = $("#q-answers");
  answers.innerHTML = "";
  if (settings.mode === "number") {
    answers.className = "numeric";
    answers.innerHTML = `
      <input id="q-number" type="text" inputmode="decimal" placeholder="Введите число" autocomplete="off">
      <button class="btn" id="q-submit">Ответить</button>`;
    const input = $("#q-number");
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") submitAnswer(input.value);
    });
    $("#q-submit").addEventListener("click", () => submitAnswer(input.value));
    input.focus();
  } else {
    answers.className = "answers";
    question.options.forEach((text, index) => {
      const button = document.createElement("button");
      button.className = "answer";
      button.innerHTML = `<span class="letter">${LETTERS[index]}</span><span class="text"></span>`;
      button.querySelector(".text").textContent = text;
      button.addEventListener("click", () => submitAnswer(index));
      attachTilt(button);
      answers.appendChild(button);
    });
  }

  startTimer(question.time_limit);
}

function updateStreak(streak) {
  $("#q-streak").textContent = streak;
  const stat = $("#q-streak-stat");
  const flame = $("#q-flame");
  const hot = streak >= 2;
  stat.classList.toggle("hot", hot);
  flame.style.display = hot ? "inline-block" : "none";
}

function renderProgress(index, total) {
  const bar = $("#q-progress");
  bar.innerHTML = "";
  const shown = Math.min(total, 50);
  for (let i = 0; i < shown; i += 1) {
    const dot = document.createElement("i");
    if (i < index) dot.classList.add("done");
    else if (i === index) dot.classList.add("now");
    bar.appendChild(dot);
  }
}

/* --------------------------------------------------------------- timer */
function startTimer(seconds) {
  const bar = $("#q-timerbar");
  const fill = bar.querySelector("i");
  const chip = $("#q-timer-stat");
  const readout = $("#q-timer");
  const started = Date.now();
  questionStartedAt = started;
  bar.classList.remove("low");
  chip.classList.remove("low");
  fill.style.transform = "scaleX(1)";
  readout.textContent = String(seconds);
  clearInterval(timerHandle);
  timerHandle = setInterval(() => {
    const left = Math.max(0, seconds - (Date.now() - started) / 1000);
    fill.style.transform = `scaleX(${left / seconds})`;
    readout.textContent = String(Math.ceil(left));
    const low = left <= 5;
    bar.classList.toggle("low", low);
    chip.classList.toggle("low", low);
    if (left <= 0) {
      clearInterval(timerHandle);
      submitAnswer(settings.mode === "number" ? "" : -1);
    }
  }, 100);
}

/* -------------------------------------------------------------- answer */
async function submitAnswer(value) {
  if (submitting) return;
  submitting = true;
  clearInterval(timerHandle);

  const elapsed = (Date.now() - questionStartedAt) / 1000;
  const data = await postJSON("/api/answer", { answer: value, elapsed });
  if (data.error) {
    window.alert(data.error);
    showScreen("home");
    return;
  }
  renderFeedback(data);
}

function renderFeedback(data) {
  animateNumber($("#q-score"), lastScore, data.score);
  lastScore = data.score;
  updateStreak(data.streak);

  // rebuild the answer block for the feedback state
  const answers = $("#q-answers");
  answers.className = "answers";
  answers.innerHTML = "";
  data.options.forEach((text, index) => {
    const button = document.createElement("button");
    button.className = "answer";
    button.innerHTML = `<span class="letter">${LETTERS[index]}</span><span class="text"></span>`;
    button.querySelector(".text").textContent = text;
    button.disabled = true;
    if (index === data.correct_index) button.classList.add("right");
    answers.appendChild(button);
  });
  const buttons = answers.querySelectorAll(".answer");
  if (settings.mode === "buttons") {
    const chosen = data.given_index;
    if (Number.isInteger(chosen) && buttons[chosen] && chosen !== data.correct_index) {
      buttons[chosen].classList.add("wrong");
    }
  }
  if (data.correct && buttons[data.correct_index]) {
    burstFrom(buttons[data.correct_index], "#47b04a");
  }

  const feedback = document.createElement("div");
  feedback.className = `feedback ${data.correct ? "good" : "bad"}`;

  const title = document.createElement("h4");
  title.textContent = data.correct
    ? `Верно! +${data.points} очков`
    : `Не угадал — правильный ответ: ${data.correct_text}`;
  feedback.appendChild(title);

  const sub = document.createElement("p");
  sub.textContent = data.correct
    ? `Ответ: ${data.correct_text} · ${data.elapsed.toFixed(1)} с`
    : `Твой ответ: ${data.given || "—"} · ${data.elapsed.toFixed(1)} с`;
  feedback.appendChild(sub);

  if (data.detail && data.detail.length) {
    const sheet = document.createElement("div");
    sheet.className = "sheet";
    data.detail.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "sheet-row";
      row.style.animationDelay = `${index * 45}ms`;
      row.innerHTML = `<span class="s-label"></span><span class="s-value"><b></b><em></em></span>`;
      row.querySelector(".s-label").textContent = entry.label;
      row.querySelector("b").textContent = entry.value;
      const bonus = row.querySelector("em");
      if (entry.bonus) {
        const sign = entry.bonus.trim().startsWith("-") ? "" : "+";
        bonus.textContent = `${sign}${entry.bonus} на след. тире`;
      } else {
        bonus.remove();
      }
      sheet.appendChild(row);
    });
    feedback.appendChild(sheet);
  }

  const next = document.createElement("button");
  next.className = "btn";
  next.textContent = data.done ? "🏁 К результатам" : "Следующий вопрос →";
  next.addEventListener("click", () => {
    if (data.done) {
      renderResult(data.summary);
      showScreen("result");
    } else {
      renderQuestion(data.next);
    }
  });
  feedback.appendChild(next);

  $("#q-feedback").innerHTML = "";
  $("#q-feedback").appendChild(feedback);
  next.focus();
}

/* -------------------------------------------------------------- result */
function renderResult(summary) {
  animateNumber($("#r-score"), 0, summary.score, 900);
  $("#r-correct").textContent = `${summary.correct}/${summary.total}`;
  $("#r-accuracy").textContent = `${summary.accuracy}%`;
  $("#r-streak").textContent = summary.best_streak;
  $("#r-time").textContent = summary.duration;
  $("#r-rank").textContent = rankFor(summary.accuracy, summary.best_streak);

  const previousBest = Number((document.cookie.match(/dq_best=(\d+)/) || [])[1] || 0);
  if (summary.score > previousBest) {
    const record = document.createElement("div");
    record.className = "notice";
    record.style.cssText = "text-align:center;margin-bottom:18px;color:#ffe9c2";
    record.textContent = "🏆 Новый рекорд!";
    $("#r-mistakes").before(record);
  }

  const ring = $("#r-ring");
  ring.style.strokeDashoffset = String(RING_CIRC);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      ring.style.strokeDashoffset = String(RING_CIRC * (1 - summary.accuracy / 100));
    });
  });

  const box = $("#r-mistakes");
  box.innerHTML = "";
  if (summary.mistakes && summary.mistakes.length) {
    const title = document.createElement("h4");
    title.style.cssText = "margin:0 0 10px;font-size:14px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)";
    title.textContent = `Ошибки (${summary.mistakes.length})`;
    const list = document.createElement("div");
    list.className = "mistakes";
    summary.mistakes.forEach((mistake, index) => {
      const row = document.createElement("div");
      row.className = "mistake";
      row.style.animationDelay = `${index * 50}ms`;
      row.innerHTML = `
        <img alt="">
        <div>
          <div class="m-item"></div>
          <div class="m-prompt"></div>
        </div>
        <div class="m-answer"><span></span><br><b></b></div>`;
      row.querySelector("img").src = mistake.image || "";
      row.querySelector("img").alt = mistake.item_name;
      row.querySelector(".m-item").textContent = mistake.item_name;
      row.querySelector(".m-prompt").textContent = mistake.prompt;
      row.querySelector(".m-answer span").textContent = `ты: ${mistake.given || "—"}`;
      row.querySelector(".m-answer b").textContent = `верно: ${mistake.correct_text}`;
      list.appendChild(row);
    });
    box.append(title, list);
  } else {
    const perfect = document.createElement("div");
    perfect.className = "notice";
    perfect.style.textAlign = "center";
    perfect.textContent = "🏆 Идеальная игра — все ответы верные!";
    box.appendChild(perfect);
  }
}

/* ---------------------------------------------------------------- hint */
async function askHint() {
  let data;
  try {
    const response = await fetch("/api/hint", { headers: { Accept: "application/json" } });
    data = await response.json().catch(() => ({ error: "Сервер вернул неожиданный ответ" }));
    if (!response.ok && !data.error) data.error = `Ошибка ${response.status}`;
  } catch (err) {
    data = { error: "Нет связи с сервером. Попробуйте ещё раз." };
  }
  if (data.error) {
    $("#q-hint-text").textContent = data.error;
    return;
  }
  if (data.hint) {
    $("#q-hint-text").textContent = data.hint;
    $("#q-hint-btn").disabled = true;
  }
}

/* --------------------------------------------------------------- setup */
setupSegmented("opt-slot", (value) => { settings.slot = value; });
setupSegmented("opt-mode", (value) => { settings.mode = value; });
setupSegmented("opt-length", (value) => { settings.length = parseInt(value, 10); });

$("#start-btn").addEventListener("click", startGame);
$("#r-again").addEventListener("click", startGame);
$("#r-home").addEventListener("click", () => showScreen("home"));
$("#q-hint-btn").addEventListener("click", askHint);
