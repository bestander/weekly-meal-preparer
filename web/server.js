import express from "express";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { loadCatalog, getMealBySlug, writeCurrentWeek } from "./lib/catalog.js";
import { loadPlanning, savePlanning, getWeek, upsertWeek, mealLastCooked, weeksSince } from "./lib/storage.js";
import { suggestMeals, suggestReplacement } from "./lib/planner.js";
import { getSessionStatus, runAuthLogin, runPurchase } from "./lib/amazon.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const PUBLIC = path.join(__dirname, "public");
const IMAGES_DIR = path.join(ROOT, "recipes", "images");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(PUBLIC));

function nextMonday(from = new Date()) {
  const d = new Date(from);
  const day = d.getDay();
  const daysUntil = day === 0 ? 1 : day === 1 ? 7 : 8 - day;
  d.setDate(d.getDate() + daysUntil);
  return d.toISOString().slice(0, 10);
}

function enrichWeek(week, planning, catalog) {
  const meals = (week.mealNames || []).map((name) => {
    const meal = catalog.find((m) => m.name === name);
    const lastWeek = mealLastCooked(
      { weeks: planning.weeks.filter((w) => w.week !== week.week) },
      name
    );
    return {
      name,
      slug: meal?.slug,
      protein: meal?.protein,
      starch: meal?.starch,
      cuisine: meal?.cuisine,
      weeksSinceCooked: weeksSince(week.week, lastWeek),
      images: meal?.images,
    };
  });
  return { ...week, meals };
}

// --- API ---

app.get("/api/settings", (_req, res) => {
  res.json(loadPlanning().settings);
});

app.put("/api/settings", (req, res) => {
  const planning = loadPlanning();
  planning.settings = { ...planning.settings, ...req.body };
  savePlanning(planning);
  res.json(planning.settings);
});

app.get("/api/catalog", (_req, res) => {
  const catalog = loadCatalog();
  res.json(
    catalog.map(({ slug, name, protein, starch, cuisine, staples, images, servings, sourceWeek }) => ({
      slug, name, protein, starch, cuisine, staples, images, servings, sourceWeek,
    }))
  );
});

app.get("/api/recipes/:slug", (req, res) => {
  const meal = getMealBySlug(req.params.slug);
  if (!meal) return res.status(404).json({ error: "Recipe not found" });
  res.json(meal);
});

app.get("/api/images/:slug/:type", (req, res) => {
  const { slug, type } = req.params;
  if (!["ingredients", "instructions"].includes(type)) {
    return res.status(400).json({ error: "Invalid image type" });
  }
  const filePath = path.join(IMAGES_DIR, `${slug}-${type}.jpg`);
  if (!fs.existsSync(filePath)) return res.status(404).json({ error: "Image not found" });
  res.sendFile(filePath);
});

app.get("/api/weeks", (_req, res) => {
  const planning = loadPlanning();
  const catalog = loadCatalog();
  res.json({
    settings: planning.settings,
    weeks: planning.weeks.map((w) => enrichWeek(w, planning, catalog)),
    upcoming: nextMonday(),
  });
});

app.get("/api/weeks/:date", (req, res) => {
  const planning = loadPlanning();
  const catalog = loadCatalog();
  const week = getWeek(planning, req.params.date);
  if (!week) return res.status(404).json({ error: "Week not found" });
  res.json(enrichWeek(week, planning, catalog));
});

app.post("/api/weeks/:date/suggest", (req, res) => {
  const planning = loadPlanning();
  const catalog = loadCatalog();
  const count = req.body.count || planning.settings.mealsPerWeek;
  const names = suggestMeals(catalog, planning, req.params.date, count);
  res.json({ mealNames: names });
});

app.post("/api/weeks/:date/suggest-replace", (req, res) => {
  const planning = loadPlanning();
  const catalog = loadCatalog();
  const { mealNames, replaceIndex } = req.body;
  const names = suggestReplacement(catalog, planning, req.params.date, mealNames, replaceIndex);
  res.json({ mealNames: names });
});

app.put("/api/weeks/:date", (req, res) => {
  const planning = loadPlanning();
  const { mealNames, status } = req.body;
  const entry = {
    week: req.params.date,
    mealNames,
    status: status || "planned",
    updatedAt: new Date().toISOString(),
  };
  const existing = getWeek(planning, req.params.date);
  if (!existing) entry.createdAt = entry.updatedAt;
  upsertWeek(planning, entry);

  if (mealNames?.length) {
    writeCurrentWeek(req.params.date, mealNames);
  }

  savePlanning(planning);
  const catalog = loadCatalog();
  res.json(enrichWeek(getWeek(planning, req.params.date), planning, catalog));
});

app.get("/api/amazon/status", (_req, res) => {
  res.json(getSessionStatus());
});

const activeJobs = new Map();

app.post("/api/amazon/auth", async (_req, res) => {
  const jobId = `auth-${Date.now()}`;
  const log = [];
  activeJobs.set(jobId, { type: "auth", log, done: false });

  res.json({ jobId, message: "Browser will open for Amazon login. Close it when done." });

  runAuthLogin((stream, text) => {
    log.push({ stream, text, at: new Date().toISOString() });
  }).then((result) => {
    activeJobs.set(jobId, { type: "auth", log, done: true, result });
  });
});

app.post("/api/purchase/run", async (req, res) => {
  const planning = loadPlanning();
  const current = planning.weeks
    .filter((w) => w.mealNames?.length)
    .sort((a, b) => (b.updatedAt || b.week).localeCompare(a.updatedAt || a.week))[0];
  if (!current?.mealNames?.length) {
    return res.status(400).json({ error: "No planned week with meals. Save a week plan first." });
  }

  writeCurrentWeek(current.week, current.mealNames);

  const jobId = `purchase-${Date.now()}`;
  const log = [];
  activeJobs.set(jobId, { type: "purchase", log, done: false });

  res.json({
    jobId,
    week: current.week,
    meals: current.mealNames,
    message: "Purchase started. Specialty items may need approval in the terminal.",
  });

  const checkout = req.body?.checkout === true;
  runPurchase((stream, text) => {
    log.push({ stream, text, at: new Date().toISOString() });
  }, checkout).then((result) => {
    activeJobs.set(jobId, { type: "purchase", log, done: true, result });
    if (result.code === 0) {
      const p = loadPlanning();
      const w = getWeek(p, current.week);
      if (w) {
        upsertWeek(p, { ...w, status: "ordered", orderedAt: new Date().toISOString() });
        savePlanning(p);
      }
    }
  });
});

app.get("/api/jobs/:id", (req, res) => {
  const job = activeJobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: "Job not found" });
  res.json(job);
});

app.get("*", (_req, res) => {
  res.sendFile(path.join(PUBLIC, "index.html"));
});

app.listen(PORT, () => {
  console.log(`Meal Rotation UI: http://localhost:${PORT}`);
});
