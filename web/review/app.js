const state = {
  rows: [],
  filteredRows: [],
  selectedId: null,
  originalRow: null,
  isEditing: false,
  expandedGames: {},
};

const coreFields = ["quarter", "clock", "down", "distance", "offense_score", "defense_score"];

const numberFields = new Set([
  "start_sec",
  "end_sec",
  "quarter",
  "down",
  "distance",
  "offense_score",
  "defense_score",
  "offense_score_confidence",
  "defense_score_confidence",
  "clock_confidence",
  "quarter_confidence",
  "down_confidence",
  "distance_confidence",
  "field_position_confidence",
  "play_art_confidence",
  "play_art_sample_time_sec",
  "ocr_sample_time_sec",
  "score_sample_time_sec",
]);

const boolFields = new Set([
  "score_imputed_from_previous",
  "play_art_visible",
]);

const statusEl = document.getElementById("status");
const playListEl = document.getElementById("playList");
const searchEl = document.getElementById("search");
const detailTitleEl = document.getElementById("detailTitle");
const detailFormEl = document.getElementById("detailForm");
const videoEl = document.getElementById("video");
const editBtn = document.getElementById("editBtn");
const saveBtn = document.getElementById("saveBtn");
const resetBtn = document.getElementById("resetBtn");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#b00020" : "";
}

async function loadRows() {
  setStatus("Loading plays...");
  const resp = await fetch("/api/plays");
  if (!resp.ok) {
    throw new Error(`Failed to load plays (${resp.status})`);
  }
  const payload = await resp.json();
  state.rows = payload.rows || [];
  state.filteredRows = [...state.rows];

  if (!state.rows.length) {
    setStatus("No plays found.");
    return;
  }

  state.selectedId = state.rows[0].play_id;
  renderList();
  renderDetails();
  setStatus(`Loaded ${state.rows.length} plays.`);
}

function getSelectedRow() {
  return state.rows.find((row) => row.play_id === state.selectedId) || null;
}

function isCompleteNoReview(row) {
  return row.quality_flag === "ok" && coreFields.every((field) => row[field] !== null && row[field] !== undefined);
}

function groupRowsByGame(rows) {
  const groups = new Map();
  for (const row of rows) {
    const gameId = row.game_id || "unknown_game";
    if (!groups.has(gameId)) {
      groups.set(gameId, []);
    }
    groups.get(gameId).push(row);
  }
  return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
}

function getGameStats(gameId) {
  const gameRows = state.rows.filter((row) => (row.game_id || "unknown_game") === gameId);
  const complete = gameRows.filter(isCompleteNoReview).length;
  const total = gameRows.length;
  return { complete, total, remaining: Math.max(0, total - complete) };
}

function toggleGame(gameId) {
  const current = state.expandedGames[gameId];
  state.expandedGames[gameId] = current === undefined ? false : !current;
  renderList();
}

function filterRows(query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    state.filteredRows = [...state.rows];
  } else {
    state.filteredRows = state.rows.filter((row) => {
      const a = String(row.play_id || "").toLowerCase();
      const b = String(row.game_id || "").toLowerCase();
      return a.includes(normalized) || b.includes(normalized);
    });
    for (const row of state.filteredRows) {
      const gameId = row.game_id || "unknown_game";
      state.expandedGames[gameId] = true;
    }
  }

  if (!state.filteredRows.some((row) => row.play_id === state.selectedId) && state.filteredRows.length) {
    state.selectedId = state.filteredRows[0].play_id;
  }

  renderList();
  renderDetails();
}

function renderList() {
  playListEl.innerHTML = "";
  const grouped = groupRowsByGame(state.filteredRows);
  for (const [gameId, rows] of grouped) {
    const stats = getGameStats(gameId);
    const ratio = stats.total ? (stats.complete / stats.total) * 100 : 0;
    if (state.expandedGames[gameId] === undefined) {
      state.expandedGames[gameId] = true;
    }
    const expanded = state.expandedGames[gameId];

    const groupItem = document.createElement("li");
    groupItem.className = "game-group";

    const gameBtn = document.createElement("button");
    gameBtn.type = "button";
    gameBtn.className = "game-header";
    gameBtn.innerHTML = `
      <div class="game-left">
        <span class="chevron">${expanded ? "▾" : "▸"}</span>
        <strong>${gameId}</strong>
      </div>
      <div class="game-right">
        <div class="game-progress">
          <span
            class="donut"
            style="--pct:${ratio.toFixed(1)}%"
            aria-label="${stats.complete} complete of ${stats.total}"
            title="${stats.complete}/${stats.total} complete"
          ></span>
          <span class="game-progress-text">${stats.complete}/${stats.total}</span>
        </div>
      </div>
    `;
    gameBtn.addEventListener("click", () => toggleGame(gameId));
    groupItem.appendChild(gameBtn);

    const playsList = document.createElement("ul");
    playsList.className = "group-plays";
    playsList.style.display = expanded ? "block" : "none";

    for (const row of rows) {
      const li = document.createElement("li");
      li.className = "play-item" + (row.play_id === state.selectedId ? " active" : "");
      if (isCompleteNoReview(row)) {
        li.className += " complete";
      }
      const statusBadge = isCompleteNoReview(row)
        ? '<span class="badge badge-done">Complete</span>'
        : '<span class="badge badge-review">Needs Review</span>';
      li.innerHTML = `
        <div class="play-head">
          <strong>${row.play_id || "(missing play_id)"}</strong>
          ${statusBadge}
        </div>
        <div class="meta">quality=${row.quality_flag ?? "null"}</div>
      `;
      li.addEventListener("click", () => {
        state.selectedId = row.play_id;
        state.isEditing = false;
        state.originalRow = null;
        renderList();
        renderDetails();
      });
      playsList.appendChild(li);
    }

    groupItem.appendChild(playsList);
    playListEl.appendChild(groupItem);
  }
}

function inferType(key, value) {
  if (boolFields.has(key) || typeof value === "boolean") {
    return "bool";
  }
  if (numberFields.has(key) || typeof value === "number") {
    return "number";
  }
  return "text";
}

function createInput(key, value, enabled) {
  const wrap = document.createElement("div");
  wrap.className = "field";

  const label = document.createElement("label");
  label.textContent = key;
  wrap.appendChild(label);

  const inputRow = document.createElement("div");
  inputRow.className = "inline";
  const kind = inferType(key, value);

  let input;
  if (kind === "bool") {
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
  } else {
    input = document.createElement("input");
    input.type = kind === "number" ? "number" : "text";
    if (value !== null && value !== undefined) {
      input.value = String(value);
    }
  }

  input.dataset.key = key;
  input.dataset.kind = kind;
  input.disabled = !enabled;
  inputRow.appendChild(input);

  const nullLabel = document.createElement("label");
  nullLabel.style.fontSize = "12px";
  const nullBox = document.createElement("input");
  nullBox.type = "checkbox";
  nullBox.checked = value === null || value === undefined;
  nullBox.disabled = !enabled;

  nullBox.addEventListener("change", () => {
    if (kind === "bool") {
      input.disabled = nullBox.checked || !state.isEditing;
      if (nullBox.checked) {
        input.checked = false;
      }
      return;
    }
    input.disabled = nullBox.checked || !state.isEditing;
    if (nullBox.checked) {
      input.value = "";
    }
  });

  nullLabel.appendChild(nullBox);
  nullLabel.appendChild(document.createTextNode(" null"));
  inputRow.appendChild(nullLabel);

  wrap.appendChild(inputRow);
  return wrap;
}

function renderDetails() {
  const row = getSelectedRow();
  detailFormEl.innerHTML = "";

  if (!row) {
    detailTitleEl.textContent = "Details";
    videoEl.removeAttribute("src");
    return;
  }

  detailTitleEl.textContent = row.play_id || "Details";
  const keys = Object.keys(row);
  const preferredOrder = [
    "play_id",
    "game_id",
    "clip_path",
    "source_video",
    "start_sec",
    "end_sec",
    "label_priority",
    "selection_reason",
    "quarter",
    "clock",
    "down",
    "distance",
    "offense_score",
    "defense_score",
    "quality_flag",
  ];

  keys.sort((a, b) => {
    const ai = preferredOrder.indexOf(a);
    const bi = preferredOrder.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });

  for (const key of keys) {
    detailFormEl.appendChild(createInput(key, row[key], state.isEditing));
  }

  const clipPath = row.clip_path;
  if (clipPath) {
    videoEl.src = `/api/clip?path=${encodeURIComponent(clipPath)}`;
  } else {
    videoEl.removeAttribute("src");
  }

  editBtn.disabled = false;
  saveBtn.disabled = !state.isEditing;
  resetBtn.disabled = !state.isEditing;
}

function collectFormRow() {
  const row = {};
  const inputs = detailFormEl.querySelectorAll("input[data-key]");

  for (const input of inputs) {
    const key = input.dataset.key;
    const kind = input.dataset.kind;
    const nullToggle = input.parentElement.querySelector('label input[type="checkbox"]');
    const isNull = nullToggle ? nullToggle.checked : false;

    if (isNull) {
      row[key] = null;
      continue;
    }

    if (kind === "bool") {
      row[key] = Boolean(input.checked);
      continue;
    }

    const raw = input.value;
    if (kind === "number") {
      if (raw === "") {
        row[key] = null;
      } else {
        const parsed = Number(raw);
        row[key] = Number.isNaN(parsed) ? null : parsed;
      }
      continue;
    }

    row[key] = raw;
  }
  return row;
}

editBtn.addEventListener("click", () => {
  const row = getSelectedRow();
  if (!row) return;
  state.isEditing = true;
  state.originalRow = structuredClone(row);
  renderDetails();
  setStatus(`Editing ${row.play_id}`);
});

resetBtn.addEventListener("click", () => {
  const row = getSelectedRow();
  if (!row || !state.originalRow) return;
  const idx = state.rows.findIndex((r) => r.play_id === row.play_id);
  if (idx >= 0) {
    state.rows[idx] = structuredClone(state.originalRow);
  }
  state.isEditing = false;
  state.originalRow = null;
  renderList();
  renderDetails();
  setStatus("Reset unsaved edits.");
});

saveBtn.addEventListener("click", async () => {
  const row = getSelectedRow();
  if (!row) return;

  const updated = collectFormRow();
  setStatus("Saving...");
  const resp = await fetch(`/api/play/${encodeURIComponent(row.play_id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  });

  if (!resp.ok) {
    setStatus(`Save failed (${resp.status})`, true);
    return;
  }

  const payload = await resp.json();
  const idx = state.rows.findIndex((r) => r.play_id === row.play_id);
  if (idx >= 0) {
    state.rows[idx] = payload.row;
  }
  state.isEditing = false;
  state.originalRow = null;
  renderList();
  renderDetails();
  setStatus(`Saved ${row.play_id}`);
});

searchEl.addEventListener("input", (event) => {
  filterRows(event.target.value);
});

(async function bootstrap() {
  try {
    await loadRows();
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
})();
