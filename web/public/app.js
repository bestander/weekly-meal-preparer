import { h, render } from "https://esm.sh/preact@10.26.4";
import { useState, useEffect, useCallback, useRef } from "https://esm.sh/preact@10.26.4/hooks";
import htm from "https://esm.sh/htm@3.1.1";

const html = htm.bind(h);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

function Tag({ label, variant }) {
  return html`<span class="tag tag-${variant || "default"}">${label}</span>`;
}

function Nav({ route, setRoute }) {
  const links = [
    ["plan", "Plan"],
    ["history", "History"],
    ["purchase", "Purchase"],
    ["settings", "Settings"],
  ];
  const cropHref = "/crop.html";
  return html`
    <nav class="nav">
      <a class="brand" href="#" onClick=${(e) => { e.preventDefault(); setRoute("plan"); }}>
        Meal Rotation
      </a>
      <div class="nav-links">
        ${links.map(([id, label]) => html`
          <button
            class=${route === id ? "nav-link active" : "nav-link"}
            onClick=${() => setRoute(id)}
          >${label}</button>
        `)}
        <a class="nav-link" href=${cropHref}>Crop images</a>
      </div>
    </nav>
  `;
}

function MealCard({ meal, onView, onSwap, showSwap }) {
  return html`
    <article class="meal-card">
      ${meal.images?.ingredients && html`
        <img
          class="meal-thumb meal-thumb-clickable"
          src="/api/images/${meal.slug}/ingredients"
          alt="Ingredients"
          onClick=${() => onView(meal.slug, "ingredients")}
        />
      `}
      <div class="meal-card-body">
        <h3>${meal.name}</h3>
        <div class="tags">
          <${Tag} label=${meal.protein} variant="protein" />
          <${Tag} label=${meal.starch} variant="starch" />
          ${meal.cuisine !== "other" && html`<${Tag} label=${meal.cuisine} variant="cuisine" />`}
          ${meal.weeksSinceCooked === Infinity
            ? html`<${Tag} label="never cooked" variant="new" />`
            : html`<${Tag} label=${`${meal.weeksSinceCooked}w ago`} variant="history" />`}
        </div>
        <div class="meal-actions">
          <button class="btn btn-ghost" onClick=${() => onView(meal.slug)}>View recipe</button>
          ${showSwap && html`
            <button class="btn btn-ghost" onClick=${onSwap}>Swap</button>
          `}
        </div>
      </div>
    </article>
  `;
}

function PlanView({ setRoute }) {
  const [data, setData] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [weekDate, setWeekDate] = useState("");
  const [mealNames, setMealNames] = useState([]);
  const [saving, setSaving] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [swapIndex, setSwapIndex] = useState(null);
  const [error, setError] = useState("");

  const loadWeekMeals = useCallback(async (target, weeksData) => {
    const existing = weeksData.weeks.find((w) => w.week === target);
    if (existing?.mealNames?.length) {
      setMealNames(existing.mealNames);
    } else {
      const suggested = await api(`/api/weeks/${target}/suggest`, { method: "POST" });
      setMealNames(suggested.mealNames);
    }
  }, []);

  const load = useCallback(async () => {
    const [weeks, cat] = await Promise.all([api("/api/weeks"), api("/api/catalog")]);
    setData(weeks);
    setCatalog(cat);
    const target = weeks.upcoming;
    setWeekDate(target);
    await loadWeekMeals(target, weeks);
  }, [loadWeekMeals]);

  const skipWeekReload = useRef(true);

  useEffect(() => { load().catch((e) => setError(e.message)); }, [load]);

  useEffect(() => {
    if (!data || !weekDate) return;
    if (skipWeekReload.current) {
      skipWeekReload.current = false;
      return;
    }
    loadWeekMeals(weekDate, data).catch((e) => setError(e.message));
  }, [weekDate]);

  const catalogByName = new Map(catalog.map((m) => [m.name, m]));
  const meals = mealNames.map((name) => {
    const fromCatalog = catalogByName.get(name);
    const fromWeek = data?.weeks.find((w) => w.week === weekDate);
    const enriched = fromWeek?.meals?.find((m) => m.name === name);
    return {
      name,
      slug: fromCatalog?.slug,
      protein: fromCatalog?.protein || enriched?.protein || "?",
      starch: fromCatalog?.starch || enriched?.starch || "?",
      cuisine: fromCatalog?.cuisine || enriched?.cuisine || "other",
      weeksSinceCooked: enriched?.weeksSinceCooked ?? Infinity,
      images: fromCatalog?.images || enriched?.images,
    };
  });

  async function suggestAll() {
    const res = await api(`/api/weeks/${weekDate}/suggest`, {
      method: "POST",
      body: { randomize: true },
    });
    setMealNames(res.mealNames);
  }

  async function swapMeal(index) {
    const res = await api(`/api/weeks/${weekDate}/suggest-replace`, {
      method: "POST",
      body: { mealNames, replaceIndex: index },
    });
    setMealNames(res.mealNames);
  }

  async function saveWeek() {
    setSaving(true);
    try {
      await api(`/api/weeks/${weekDate}`, {
        method: "PUT",
        body: { mealNames, status: "planned" },
      });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function pickMeal(name) {
    const next = [...mealNames];
    next[swapIndex] = name;
    setMealNames(next);
    setPickerOpen(false);
    setSwapIndex(null);
  }

  if (!data) return html`<div class="loading">Loading…</div>`;

  return html`
    <section class="view">
      <header class="view-header">
        <div>
          <h1>This week</h1>
          <p class="subtitle">Plan ${data.settings.mealsPerWeek} meals with variety and shared staples</p>
        </div>
        <div class="week-picker">
          <label>Week of</label>
          <input type="date" value=${weekDate} onInput=${(e) => setWeekDate(e.target.value)} />
        </div>
      </header>

      ${error && html`<div class="alert alert-error">${error}</div>`}

      <div class="toolbar">
        <button class="btn" onClick=${suggestAll}>Suggest meals</button>
        <button class="btn btn-primary" onClick=${saveWeek} disabled=${saving}>
          ${saving ? "Saving…" : "Save week plan"}
        </button>
      </div>

      <div class="meal-grid">
        ${meals.map((meal, i) => html`
          <${MealCard}
            key=${meal.name}
            meal=${meal}
            onView=${(slug, tab) => slug && setRoute("recipe", slug, tab)}
            onSwap=${() => swapMeal(i)}
            showSwap=${true}
          />
        `)}
        ${mealNames.length < data.settings.mealsPerWeek && html`
          <div class="meal-card meal-card-empty">
            <p>Need ${data.settings.mealsPerWeek - mealNames.length} more meal(s)</p>
            <button class="btn" onClick=${suggestAll}>Add suggestion</button>
          </div>
        `}
      </div>

      <div class="manual-pick">
        <h2>Manual swap</h2>
        <p>Pick a slot, then choose any recipe from the catalog.</p>
        <div class="slot-buttons">
          ${mealNames.map((name, i) => html`
            <button
              class="btn btn-ghost"
              onClick=${() => { setSwapIndex(i); setPickerOpen(true); }}
            >Slot ${i + 1}: ${name.slice(0, 30)}…</button>
          `)}
        </div>
      </div>

      ${pickerOpen && html`
        <${CatalogPicker}
          onPick=${pickMeal}
          onClose=${() => { setPickerOpen(false); setSwapIndex(null); }}
          exclude=${mealNames}
        />
      `}
    </section>
  `;
}

function ImageLightbox({ src, alt, onClose }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return html`
    <div class="image-lightbox-overlay" onClick=${onClose} role="dialog" aria-modal="true">
      <button class="image-lightbox-close btn btn-ghost" onClick=${onClose} aria-label="Close">×</button>
      <img
        class="image-lightbox-img"
        src=${src}
        alt=${alt}
        onClick=${(e) => e.stopPropagation()}
      />
    </div>
  `;
}

function CatalogPicker({ onPick, onClose, exclude }) {
  const [catalog, setCatalog] = useState([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api("/api/catalog").then(setCatalog);
  }, []);

  const excludeSet = new Set(exclude || []);
  const filtered = catalog.filter((m) => {
    if (excludeSet.has(m.name)) return false;
    if (!filter) return true;
    const q = filter.toLowerCase();
    return m.name.toLowerCase().includes(q) || m.protein.includes(q) || m.cuisine.includes(q);
  });

  return html`
    <div class="modal-overlay" onClick=${onClose}>
      <div class="modal" onClick=${(e) => e.stopPropagation()}>
        <header class="modal-header">
          <h2>Choose a recipe</h2>
          <button class="btn btn-ghost" onClick=${onClose}>Close</button>
        </header>
        <input
          class="search-input"
          placeholder="Search by name, protein, cuisine…"
          value=${filter}
          onInput=${(e) => setFilter(e.target.value)}
        />
        <ul class="catalog-list">
          ${filtered.map((m) => html`
            <li>
              <button class="catalog-item" onClick=${() => onPick(m.name)}>
                <span class="catalog-name">${m.name}</span>
                <span class="tags">
                  <${Tag} label=${m.protein} variant="protein" />
                  <${Tag} label=${m.starch} variant="starch" />
                </span>
              </button>
            </li>
          `)}
        </ul>
      </div>
    </div>
  `;
}

function RecipeView({ slug, goBack, initialTab = "instructions" }) {
  const [recipe, setRecipe] = useState(null);
  const [tab, setTab] = useState(initialTab);
  const [lightbox, setLightbox] = useState(null);

  useEffect(() => {
    setTab(initialTab);
  }, [slug, initialTab]);

  useEffect(() => {
    api(`/api/recipes/${slug}`).then(setRecipe).catch(() => setRecipe(null));
  }, [slug]);

  if (!recipe) return html`<div class="loading">Loading recipe…</div>`;

  return html`
    <section class="view recipe-view">
      <button class="btn btn-ghost back-btn" onClick=${goBack}>← Back</button>
      <h1>${recipe.name}</h1>
      <div class="tags">
        <${Tag} label=${recipe.protein} variant="protein" />
        <${Tag} label=${recipe.starch} variant="starch" />
        ${recipe.cuisine !== "other" && html`<${Tag} label=${recipe.cuisine} variant="cuisine" />`}
        <${Tag} label=${`${recipe.servings} servings`} variant="default" />
      </div>

      <div class="tabs">
        <button class=${tab === "instructions" ? "tab active" : "tab"} onClick=${() => setTab("instructions")}>
          Instructions
        </button>
        <button class=${tab === "ingredients" ? "tab active" : "tab"} onClick=${() => setTab("ingredients")}>
          Ingredients
        </button>
        ${recipe.nutrition && html`
          <button class=${tab === "nutrition" ? "tab active" : "tab"} onClick=${() => setTab("nutrition")}>
            Nutrition
          </button>
        `}
      </div>

      ${tab === "instructions" && html`
        <div class="recipe-content">
          ${recipe.images?.instructions && html`
            <img
              class="recipe-image recipe-image-clickable"
              src="/api/images/${recipe.slug}/instructions"
              alt="Instructions card"
              onClick=${() => setLightbox({
                src: `/api/images/${recipe.slug}/instructions`,
                alt: "Instructions card",
              })}
            />
          `}
          <ol class="steps">
            ${(recipe.instructions || []).map((step) => html`
              <li class="step">
                <h3>Step ${step.step}: ${step.title}</h3>
                <p>${step.text}</p>
              </li>
            `)}
          </ol>
        </div>
      `}

      ${tab === "ingredients" && html`
        <div class="recipe-content">
          ${recipe.images?.ingredients && html`
            <img
              class="recipe-image recipe-image-clickable"
              src="/api/images/${recipe.slug}/ingredients"
              alt="Ingredients card"
              onClick=${() => setLightbox({
                src: `/api/images/${recipe.slug}/ingredients`,
                alt: "Ingredients card",
              })}
            />
          `}
          <ul class="ingredient-list">
            ${(recipe.ingredients || []).map((ing) => html`
              <li>${ing.quantity} ${ing.unit} ${ing.name}</li>
            `)}
          </ul>
        </div>
      `}

      ${tab === "nutrition" && recipe.nutrition && html`
        <div class="nutrition-grid">
          ${Object.entries(recipe.nutrition).map(([k, v]) => html`
            <div class="nutrition-item">
              <span class="nutrition-label">${k.replace(/_/g, " ")}</span>
              <span class="nutrition-value">${v}</span>
            </div>
          `)}
        </div>
      `}

      ${lightbox && html`
        <${ImageLightbox}
          src=${lightbox.src}
          alt=${lightbox.alt}
          onClose=${() => setLightbox(null)}
        />
      `}
    </section>
  `;
}

function HistoryView({ setRoute }) {
  const [weeks, setWeeks] = useState([]);

  useEffect(() => {
    api("/api/weeks").then((d) => setWeeks(d.weeks));
  }, []);

  return html`
    <section class="view">
      <h1>Meal history</h1>
      <p class="subtitle">Past weeks and when each meal was last cooked</p>

      ${weeks.length === 0 && html`<p class="empty">No planned weeks yet.</p>`}

      <div class="history-list">
        ${weeks.map((week) => html`
          <article class="history-week" key=${week.week}>
            <header>
              <h2>Week of ${week.week}</h2>
              <${Tag} label=${week.status || "planned"} variant="default" />
            </header>
            <ul>
              ${(week.meals || []).map((meal) => html`
                <li>
                  <button class="link-btn" onClick=${() => meal.slug && setRoute("recipe", meal.slug)}>
                    ${meal.name}
                  </button>
                  <span class="meta">
                    ${meal.weeksSinceCooked === Infinity ? "first time" : `${meal.weeksSinceCooked}w since prior`}
                  </span>
                </li>
              `)}
            </ul>
          </article>
        `)}
      </div>
    </section>
  `;
}

function PurchaseView() {
  const [status, setStatus] = useState(null);
  const [job, setJob] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState("");
  const [weeks, setWeeks] = useState(null);

  const refresh = useCallback(async () => {
    const [s, w] = await Promise.all([api("/api/amazon/status"), api("/api/weeks")]);
    setStatus(s);
    setWeeks(w);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      const j = await api(`/api/jobs/${jobId}`);
      setJob(j);
      if (j.done) {
        clearInterval(interval);
        refresh();
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [jobId, refresh]);

  async function startAuth() {
    setError("");
    const res = await api("/api/amazon/auth", { method: "POST" });
    setJobId(res.jobId);
    setJob({ log: [], done: false });
  }

  async function startPurchase() {
    setError("");
    try {
      const res = await api("/api/purchase/run", { method: "POST", body: {} });
      setJobId(res.jobId);
      setJob({ log: [], done: false });
    } catch (e) {
      setError(e.message);
    }
  }

  const planned = weeks?.weeks?.find((w) => w.status === "planned") || weeks?.weeks?.[0];
  const statusLabel = {
    valid: "Connected",
    expired: "Session expired",
    missing: "Not authenticated",
  };

  return html`
    <section class="view">
      <h1>Purchase groceries</h1>
      <p class="subtitle">Amazon ordering runs via the Python CLI. Specialty items may need terminal approval.</p>

      <div class="purchase-grid">
        <article class="panel">
          <h2>Amazon session</h2>
          ${status && html`
            <div class=${`status-badge status-${status.status}`}>
              ${statusLabel[status.status]}
            </div>
            ${status.savedAt && html`
              <p class="meta">Saved ${status.ageDays} day(s) ago (max ${status.maxAgeDays})</p>
            `}
          `}
          <button class="btn" onClick=${startAuth}>Authenticate (opens browser)</button>
          <p class="hint">Log in to Amazon, confirm Whole Foods delivery, then close the browser.</p>
        </article>

        <article class="panel">
          <h2>This week's order</h2>
          ${planned ? html`
            <p>Week of <strong>${planned.week}</strong> — ${planned.mealNames?.length || 0} meals</p>
            <ul class="compact-list">
              ${(planned.mealNames || []).map((n) => html`<li>${n}</li>`)}
            </ul>
            <button class="btn btn-primary" onClick=${startPurchase} disabled=${status?.status !== "valid"}>
              Order groceries
            </button>
          ` : html`<p class="empty">Save a week plan first.</p>`}
          ${error && html`<div class="alert alert-error">${error}</div>`}
        </article>
      </div>

      ${job && html`
        <article class="panel log-panel">
          <h2>Output</h2>
          <pre class="log-output">${(job.log || []).map((l) => l.text).join("")}${job.done ? "\n[done]" : ""}</pre>
        </article>
      `}
    </section>
  `;
}

function SettingsView() {
  const [settings, setSettings] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api("/api/settings").then(setSettings);
  }, []);

  async function save() {
    await api("/api/settings", { method: "PUT", body: settings });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (!settings) return html`<div class="loading">Loading…</div>`;

  return html`
    <section class="view">
      <h1>Settings</h1>
      <div class="settings-form">
        <label>
          Meals per week
          <input
            type="number" min="1" max="7"
            value=${settings.mealsPerWeek}
            onInput=${(e) => setSettings({ ...settings, mealsPerWeek: +e.target.value })}
          />
        </label>
        <label>
          Cooldown weeks (don't repeat within)
          <input
            type="number" min="0" max="52"
            value=${settings.cooldownWeeks}
            onInput=${(e) => setSettings({ ...settings, cooldownWeeks: +e.target.value })}
          />
        </label>
        <button class="btn btn-primary" onClick=${save}>Save</button>
        ${saved && html`<span class="saved-msg">Saved!</span>`}
      </div>
    </section>
  `;
}

function App() {
  const [route, setRouteState] = useState("plan");
  const [recipeSlug, setRecipeSlug] = useState(null);
  const [recipeTab, setRecipeTab] = useState("instructions");

  function setRoute(name, slug, tab) {
    setRouteState(name);
    setRecipeSlug(slug || null);
    setRecipeTab(tab || "instructions");
    window.scrollTo(0, 0);
  }

  return html`
    <div class="app">
      <${Nav} route=${route} setRoute=${setRoute} />
      <main>
        ${route === "plan" && html`<${PlanView} setRoute=${setRoute} />`}
        ${route === "recipe" && recipeSlug && html`
          <${RecipeView} slug=${recipeSlug} initialTab=${recipeTab} goBack=${() => setRoute("plan")} />
        `}
        ${route === "history" && html`<${HistoryView} setRoute=${setRoute} />`}
        ${route === "purchase" && html`<${PurchaseView} />`}
        ${route === "settings" && html`<${SettingsView} />`}
      </main>
    </div>
  `;
}

render(html`<${App} />`, document.getElementById("app"));
