const state = {
  rows: [],
  filteredRows: [],
  selectedId: null,
  originalRow: null,
  isEditing: false,
  expandedGames: {},
  filters: {
    search: "",
    review: "all",
    playType: "all",
  },
};

const coreFields = ["quarter", "clock", "down", "distance", "home_score", "away_score"];
const routeFamilies = [
  "fade_or_go",
  "flat_or_hitch",
  "screen_or_swing",
  "cross_or_over",
  "in_or_out_break",
  "post_or_corner",
  "unknown",
];
const assignmentLabels = ["X", "Y", "A", "B", "RB"];
const clockRegex = /^[0-5]\d:[0-5]\d$/;
const reviewDispositions = new Set(["keep", "skip_unusable", "delete_candidate"]);
const reviewStates = new Set(["pending", "reviewed"]);

const fieldSpecs = {
  quarter: {
    hint: "Quarter: 1-4 (use 5 for OT if needed).",
    min: 1,
    max: 5,
    integer: true,
  },
  clock: {
    placeholder: "MM:SS (e.g. 12:34)",
    hint: "Clock must be MM:SS (00:00 to 59:59).",
    pattern: "^[0-5]\\d:[0-5]\\d$",
  },
  down: {
    hint: "Down must be 1-4.",
    min: 1,
    max: 4,
    integer: true,
  },
  distance: {
    placeholder: "e.g. 7",
    hint: "Distance must be 0-99 yards.",
    min: 0,
    max: 99,
    integer: true,
  },
  home_score: {
    hint: "Score must be a whole number from 0 to 999.",
    min: 0,
    max: 999,
    integer: true,
  },
  away_score: {
    hint: "Score must be a whole number from 0 to 999.",
    min: 0,
    max: 999,
    integer: true,
  },
  quality_flag: {
    hint: "Use only: ok, needs_review, or null.",
  },
  review_state: {
    hint: "Review lifecycle: pending or reviewed.",
  },
  review_disposition: {
    hint: "Workflow action: keep, skip_unusable, delete_candidate, or null.",
  },
  primary_route_family: {
    hint: "Main route family for this play art.",
  },
  secondary_route_family: {
    hint: "Optional second route family (or null).",
  },
  assignment_labels_expected: {
    hint: "Comma-separated labels (allowed: X, Y, A, B, RB).",
    placeholder: "X, Y, RB",
  },
  labeler_notes: {
    hint: "Optional notes on ambiguity or review rationale.",
  },
};

const numberFields = new Set([
  "start_sec",
  "end_sec",
  "quarter",
  "down",
  "distance",
  "home_score",
  "away_score",
  "home_score_confidence",
  "away_score_confidence",
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

const enumFields = {
  review_state: ["pending", "reviewed"],
  quality_flag: ["ok", "needs_review"],
  review_disposition: ["keep", "skip_unusable", "delete_candidate"],
  play_type: ["run", "pass", "kick", "rpo"],
  primary_route_family: routeFamilies,
  secondary_route_family: routeFamilies,
};
const readOnlyFields = new Set([
  "play_id",
  "game_id",
  "clip_path",
  "play_art_path",
  "source_url",
  "source_video",
  "start_sec",
  "end_sec",
  "label_priority",
  "selection_reason",
]);
const hiddenLegacyFields = new Set([
  "offense_score",
  "defense_score",
  "offense_score_confidence",
  "defense_score_confidence",
]);

const statusEl = document.getElementById("status");
const playListEl = document.getElementById("playList");
const searchEl = document.getElementById("search");
const reviewFilterEl = document.getElementById("reviewFilter");
const playTypeFilterEl = document.getElementById("playTypeFilter");
const detailTitleEl = document.getElementById("detailTitle");
const detailFormEl = document.getElementById("detailForm");
const videoEl = document.getElementById("video");
const playImageEl = document.getElementById("playImage");
const mediaHintEl = document.getElementById("mediaHint");
const editBtn = document.getElementById("editBtn");
const saveBtn = document.getElementById("saveBtn");
const resetBtn = document.getElementById("resetBtn");

function inferPlayTypeFromRow(row) {
  const text = `${row.play_slug || ""} ${row.play_name || ""} ${row.formation_slug || ""}`.toLowerCase();
  const rpoHints = ["rpo", "run_pass_option", "run-pass-option"];
  const kickHints = ["kickoff", "onside", "punt", "field_goal", "fg_", "pat", "extra_point"];
  const runHints = [
    "inside_zone",
    "outside_zone",
    "zone_split",
    "power",
    "counter",
    "draw",
    "sweep",
    "dive",
    "read_option",
    "jet",
    "trap",
    "iso",
    "duo",
  ];
  if (rpoHints.some((k) => text.includes(k))) return "rpo";
  if (kickHints.some((k) => text.includes(k))) return "kick";
  if (runHints.some((k) => text.includes(k))) return "run";
  return "pass";
}

function formatClockValue(raw) {
  const digits = String(raw || "").replace(/\D/g, "").slice(0, 4);
  if (digits.length === 0) return "";
  if (digits.length === 1) return digits;
  if (digits.length === 2) return `${digits}:`;
  return `${digits.slice(0, 2)}:${digits.slice(2)}`;
}

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
  state.rows = (payload.rows || []).map((row) => {
    const next = { ...row };
    if (next.home_score === undefined || next.home_score === null) {
      if (next.offense_score !== undefined) next.home_score = next.offense_score;
    }
    if (next.away_score === undefined || next.away_score === null) {
      if (next.defense_score !== undefined) next.away_score = next.defense_score;
    }
    if (next.home_score_confidence === undefined || next.home_score_confidence === null) {
      if (next.offense_score_confidence !== undefined) {
        next.home_score_confidence = next.offense_score_confidence;
      }
    }
    if (next.away_score_confidence === undefined || next.away_score_confidence === null) {
      if (next.defense_score_confidence !== undefined) {
        next.away_score_confidence = next.defense_score_confidence;
      }
    }
    delete next.offense_score;
    delete next.defense_score;
    delete next.offense_score_confidence;
    delete next.defense_score_confidence;

    if (next.review_state === undefined || next.review_state === null) {
      next.review_state = "pending";
    }
    if (next.review_disposition === undefined || next.review_disposition === null) {
      next.review_disposition = "keep";
    }
    const isRouteRow =
      Object.prototype.hasOwnProperty.call(next, "primary_route_family") ||
      Object.prototype.hasOwnProperty.call(next, "secondary_route_family") ||
      Object.prototype.hasOwnProperty.call(next, "assignment_labels_expected");
    if (isRouteRow && (next.play_type === undefined || next.play_type === null || next.play_type === "")) {
      next.play_type = inferPlayTypeFromRow(next);
    }
    if (isRouteRow && (next.assignment_labels_expected === undefined || next.assignment_labels_expected === null)) {
      next.assignment_labels_expected = [...assignmentLabels];
    }
    return next;
  });
  applyFilters();

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

function isReviewed(row) {
  return row.review_state === "reviewed";
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

  const sorted = Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  for (const entry of sorted) {
    entry[1].sort(comparePlayOrder);
  }
  return sorted;
}

function getGameStats(gameId) {
  const gameRows = state.rows.filter((row) => (row.game_id || "unknown_game") === gameId);
  const complete = gameRows.filter(isReviewed).length;
  const total = gameRows.length;
  return { complete, total, remaining: Math.max(0, total - complete) };
}

function toggleGame(gameId) {
  const current = state.expandedGames[gameId];
  state.expandedGames[gameId] = current === undefined ? false : !current;
  renderList();
}

function parsePlayNumber(playId) {
  const value = String(playId || "");
  const match = value.match(/:play:(\d+)/i);
  if (!match) return null;
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

function comparePlayOrder(a, b) {
  const aNum = parsePlayNumber(a.play_id);
  const bNum = parsePlayNumber(b.play_id);
  if (aNum !== null && bNum !== null) {
    return aNum - bNum;
  }
  if (aNum !== null) return -1;
  if (bNum !== null) return 1;
  return String(a.play_id || "").localeCompare(String(b.play_id || ""));
}

function applyFilters() {
  const normalized = state.filters.search.trim().toLowerCase();
  state.filteredRows = state.rows.filter((row) => {
    const matchesSearch =
      !normalized ||
      String(row.play_id || "").toLowerCase().includes(normalized) ||
      String(row.game_id || "").toLowerCase().includes(normalized);

    const matchesReview =
      state.filters.review === "all" ||
      (state.filters.review === "pending" && row.review_state !== "reviewed") ||
      (state.filters.review === "reviewed" && row.review_state === "reviewed");

    const rowPlayType = String(row.play_type || "").toLowerCase();
    const matchesPlayType =
      state.filters.playType === "all" || rowPlayType === state.filters.playType;

    return matchesSearch && matchesReview && matchesPlayType;
  });

  if (normalized || state.filters.review !== "all" || state.filters.playType !== "all") {
    for (const row of state.filteredRows) {
      const gameId = row.game_id || "unknown_game";
      state.expandedGames[gameId] = true;
    }
  }

  if (!state.filteredRows.some((row) => row.play_id === state.selectedId) && state.filteredRows.length) {
    state.selectedId = state.filteredRows[0].play_id;
  }
  if (!state.filteredRows.length) {
    state.selectedId = null;
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
      if (isReviewed(row)) {
        li.className += " complete";
      }
      let statusBadge = '<span class="badge badge-review">Pending</span>';
      if (isReviewed(row) && row.review_disposition === "skip_unusable") {
        statusBadge = '<span class="badge badge-skip">Skip</span>';
      } else if (isReviewed(row) && row.review_disposition === "delete_candidate") {
        statusBadge = '<span class="badge badge-delete">Delete?</span>';
      } else if (isReviewed(row)) {
        statusBadge = '<span class="badge badge-reviewed">Reviewed</span>';
      }
      li.innerHTML = `
        <div class="play-head">
          <strong>${row.play_id || "(missing play_id)"}</strong>
          ${statusBadge}
        </div>
        <div class="meta">${buildRowMeta(row)}</div>
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

function buildRowMeta(row) {
  const bits = [`review=${row.review_state ?? "pending"}`];
  if ("quality_flag" in row) {
    bits.push(`quality=${row.quality_flag ?? "null"}`);
  }
  if ("play_type" in row) {
    bits.push(`type=${row.play_type ?? "null"}`);
  }
  if ("primary_route_family" in row) {
    bits.push(`primary=${row.primary_route_family ?? "null"}`);
  }
  return bits.join(" • ");
}

function inferType(key, value) {
  if (key === "assignment_labels_expected") {
    return "array_text";
  }
  if (Object.hasOwn(enumFields, key)) {
    return "enum";
  }
  if (Array.isArray(value)) {
    return "array_text";
  }
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
  const fieldEditable = enabled && !readOnlyFields.has(key);

  let input;
  if (kind === "bool") {
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
  } else if (kind === "enum") {
    input = document.createElement("select");
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "(null)";
    input.appendChild(blank);
    for (const optionValue of enumFields[key]) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue;
      input.appendChild(option);
    }
    if (value !== null && value !== undefined) {
      input.value = String(value);
    }
  } else if (kind === "array_text") {
    input = document.createElement("input");
    input.type = "text";
    const spec = fieldSpecs[key];
    if (spec?.placeholder) input.placeholder = spec.placeholder;
    if (Array.isArray(value) && value.length > 0) {
      input.value = value.join(", ");
    }
  } else {
    input = document.createElement("input");
    input.type = kind === "number" ? "number" : "text";
    const spec = fieldSpecs[key];
    if (spec) {
      if (spec.placeholder) input.placeholder = spec.placeholder;
      if (spec.min !== undefined) input.min = String(spec.min);
      if (spec.max !== undefined) input.max = String(spec.max);
      if (spec.pattern) input.pattern = spec.pattern;
      if (spec.integer) input.step = "1";
    }
    if (value !== null && value !== undefined) {
      input.value = String(value);
    }
    if (key === "clock") {
      input.inputMode = "numeric";
      input.maxLength = 5;
      input.value = formatClockValue(input.value);
      input.addEventListener("input", () => {
        input.value = formatClockValue(input.value);
      });
      input.addEventListener("blur", () => {
        input.value = formatClockValue(input.value);
      });
    }
  }

  input.dataset.key = key;
  input.dataset.kind = kind;
  input.disabled = !fieldEditable;
  inputRow.appendChild(input);

  const nullLabel = document.createElement("label");
  nullLabel.style.fontSize = "12px";
  const nullBox = document.createElement("input");
  nullBox.type = "checkbox";
  nullBox.checked = value === null || value === undefined;
  nullBox.disabled = !fieldEditable;

  nullBox.addEventListener("change", () => {
    if (kind === "bool") {
      input.disabled = nullBox.checked || !fieldEditable;
      if (nullBox.checked) {
        input.checked = false;
      }
      return;
    }
    input.disabled = nullBox.checked || !fieldEditable;
    if (nullBox.checked) {
      input.value = "";
    }
  });

  // If user edits a value, treat that as explicit non-null input.
  const clearNullOnUserInput = () => {
    if (!fieldEditable) return;
    if (nullBox.checked) {
      nullBox.checked = false;
      input.disabled = false;
    }
  };
  input.addEventListener("input", clearNullOnUserInput);
  input.addEventListener("change", clearNullOnUserInput);

  nullLabel.appendChild(nullBox);
  nullLabel.appendChild(document.createTextNode(" null"));
  inputRow.appendChild(nullLabel);

  wrap.appendChild(inputRow);
  const spec = fieldSpecs[key];
  if (spec?.hint) {
    const hint = document.createElement("div");
    hint.className = "field-hint";
    hint.textContent = spec.hint;
    wrap.appendChild(hint);
  }
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
  const keys = Object.keys(row).filter((key) => !hiddenLegacyFields.has(key));
  const preferredOrder = [
    "play_id",
    "game_id",
    "clip_path",
    "play_art_path",
    "source_url",
    "source_video",
    "play_type",
    "start_sec",
    "end_sec",
    "label_priority",
    "selection_reason",
    "quarter",
    "clock",
    "down",
    "distance",
    "home_score",
    "away_score",
    "quality_flag",
    "review_disposition",
    "review_state",
    "primary_route_family",
    "secondary_route_family",
    "assignment_labels_expected",
    "labeler_notes",
  ];
  if (!keys.includes("review_state")) {
    keys.push("review_state");
  }
  if (!keys.includes("review_disposition")) {
    keys.push("review_disposition");
  }
  const isRouteRow = keys.includes("primary_route_family") || keys.includes("secondary_route_family");
  if (isRouteRow && !keys.includes("play_type")) {
    keys.push("play_type");
  }
  if (isRouteRow) {
    const gameIdx = keys.indexOf("game_id");
    if (gameIdx !== -1) {
      keys.splice(gameIdx, 1);
    }
  }

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
  const playArtPath = row.play_art_path;
  let hasMedia = false;

  if (clipPath) {
    videoEl.src = `/api/clip?path=${encodeURIComponent(clipPath)}`;
    videoEl.style.display = "block";
    hasMedia = true;
  } else {
    videoEl.removeAttribute("src");
    videoEl.style.display = "none";
  }

  if (playArtPath) {
    playImageEl.src = `/api/media?path=${encodeURIComponent(playArtPath)}`;
    playImageEl.style.display = "block";
    hasMedia = true;
  } else {
    playImageEl.removeAttribute("src");
    playImageEl.style.display = "none";
  }
  mediaHintEl.style.display = hasMedia ? "none" : "block";

  editBtn.disabled = false;
  saveBtn.disabled = !state.isEditing;
  resetBtn.disabled = !state.isEditing;
}

function collectFormRow() {
  const row = {};
  const inputs = detailFormEl.querySelectorAll("[data-key]");

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
    if (kind === "enum") {
      row[key] = raw === "" ? null : raw;
      continue;
    }
    if (kind === "array_text") {
      if (raw.trim() === "") {
        row[key] = null;
      } else {
        const tokens = raw
          .split(",")
          .map((part) => part.trim().toUpperCase())
          .filter(Boolean);
        row[key] = Array.from(new Set(tokens));
      }
      continue;
    }
    if (kind === "number") {
      if (raw === "") {
        row[key] = null;
      } else {
        const parsed = Number(raw);
        row[key] = Number.isNaN(parsed) ? null : parsed;
      }
      continue;
    }

    row[key] = raw === "" ? null : raw;
  }
  return row;
}

function clearFieldErrors() {
  const inputs = detailFormEl.querySelectorAll("[data-key]");
  for (const input of inputs) {
    input.classList.remove("input-invalid");
    input.removeAttribute("title");
  }
}

function markFieldError(key, message) {
  const input = detailFormEl.querySelector(`[data-key="${key}"]`);
  if (!input) return;
  input.classList.add("input-invalid");
  input.setAttribute("title", message);
}

function validateRow(row) {
  const errors = [];
  const intFields = [
    ["quarter", 1, 5],
    ["down", 1, 4],
    ["distance", 0, 99],
    ["home_score", 0, 999],
    ["away_score", 0, 999],
  ];

  for (const [field, min, max] of intFields) {
    const value = row[field];
    if (value === null || value === undefined) continue;
    if (!Number.isInteger(value) || value < min || value > max) {
      errors.push({ field, message: `${field} must be an integer between ${min} and ${max}.` });
    }
  }

  if (row.clock !== null && row.clock !== undefined && row.clock !== "") {
    if (typeof row.clock !== "string" || !clockRegex.test(row.clock)) {
      errors.push({ field: "clock", message: "clock must match MM:SS (example 12:34)." });
    }
  }

  if (
    row.quality_flag !== null &&
    row.quality_flag !== undefined &&
    row.quality_flag !== "" &&
    row.quality_flag !== "ok" &&
    row.quality_flag !== "needs_review"
  ) {
    errors.push({ field: "quality_flag", message: "quality_flag must be ok, needs_review, or null." });
  }

  for (const field of ["primary_route_family", "secondary_route_family"]) {
    const value = row[field];
    if (value === null || value === undefined || value === "") continue;
    if (!routeFamilies.includes(String(value))) {
      errors.push({
        field,
        message: `${field} must be one of: ${routeFamilies.join(", ")}.`,
      });
    }
  }

  const labels = row.assignment_labels_expected;
  if (labels !== null && labels !== undefined) {
    if (!Array.isArray(labels)) {
      errors.push({
        field: "assignment_labels_expected",
        message: "assignment_labels_expected must be a list or null.",
      });
    } else {
      const bad = labels.filter((label) => !assignmentLabels.includes(String(label).toUpperCase()));
      if (bad.length) {
        errors.push({
          field: "assignment_labels_expected",
          message: `assignment_labels_expected can only include: ${assignmentLabels.join(", ")}.`,
        });
      }
    }
  }

  if (
    row.review_disposition !== null &&
    row.review_disposition !== undefined &&
    row.review_disposition !== "" &&
    !reviewDispositions.has(row.review_disposition)
  ) {
    errors.push({
      field: "review_disposition",
      message: "review_disposition must be keep, skip_unusable, delete_candidate, or null.",
    });
  }

  if (
    row.review_state !== null &&
    row.review_state !== undefined &&
    row.review_state !== "" &&
    !reviewStates.has(row.review_state)
  ) {
    errors.push({
      field: "review_state",
      message: "review_state must be pending, reviewed, or null.",
    });
  }

  if (
    row.quality_flag === "ok" &&
    coreFields.some((field) => row[field] === null || row[field] === undefined)
  ) {
    errors.push({ field: "quality_flag", message: "quality_flag=ok requires all core fields to be filled." });
  }

  return errors;
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
  updated.review_state = "reviewed";
  clearFieldErrors();
  const validationErrors = validateRow(updated);
  if (validationErrors.length > 0) {
    for (const err of validationErrors) {
      markFieldError(err.field, err.message);
    }
    setStatus(`Validation failed: ${validationErrors[0].message}`, true);
    return;
  }

  setStatus("Saving...");
  const resp = await fetch(`/api/play/${encodeURIComponent(row.play_id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  });

  if (!resp.ok) {
    let message = `Save failed (${resp.status})`;
    try {
      const payload = await resp.json();
      if (payload?.error) {
        message = payload.error;
      }
      if (Array.isArray(payload?.errors)) {
        for (const err of payload.errors) {
          if (err?.field && err?.message) {
            markFieldError(err.field, err.message);
          }
        }
      }
    } catch (_) {
      // Keep default message if server doesn't return JSON.
    }
    setStatus(message, true);
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
  state.filters.search = event.target.value || "";
  applyFilters();
});

reviewFilterEl.addEventListener("change", (event) => {
  state.filters.review = event.target.value || "all";
  applyFilters();
});

playTypeFilterEl.addEventListener("change", (event) => {
  state.filters.playType = event.target.value || "all";
  applyFilters();
});

(async function bootstrap() {
  try {
    await loadRows();
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
})();
