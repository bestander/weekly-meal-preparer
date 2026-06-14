import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const PLANNING_PATH = path.join(ROOT, "data", "planning.json");

const DEFAULTS = {
  settings: {
    mealsPerWeek: 3,
    cooldownWeeks: 4,
  },
  weeks: [],
};

export function loadPlanning() {
  if (!fs.existsSync(PLANNING_PATH)) {
    return structuredClone(DEFAULTS);
  }
  const data = JSON.parse(fs.readFileSync(PLANNING_PATH, "utf8"));
  return {
    settings: { ...DEFAULTS.settings, ...data.settings },
    weeks: data.weeks || [],
  };
}

export function savePlanning(data) {
  fs.mkdirSync(path.dirname(PLANNING_PATH), { recursive: true });
  fs.writeFileSync(PLANNING_PATH, JSON.stringify(data, null, 2));
}

export function getWeek(planning, weekDate) {
  return planning.weeks.find((w) => w.week === weekDate) || null;
}

export function upsertWeek(planning, weekEntry) {
  const idx = planning.weeks.findIndex((w) => w.week === weekEntry.week);
  if (idx >= 0) {
    planning.weeks[idx] = { ...planning.weeks[idx], ...weekEntry };
  } else {
    planning.weeks.push(weekEntry);
  }
  planning.weeks.sort((a, b) => b.week.localeCompare(a.week));
  return planning;
}

export function mealLastCooked(planning, mealName) {
  for (const week of planning.weeks) {
    if (week.mealNames?.includes(mealName)) {
      return week.week;
    }
  }
  return null;
}

export function weeksSince(weekDate, lastWeek) {
  if (!lastWeek) return Infinity;
  const a = new Date(weekDate);
  const b = new Date(lastWeek);
  return Math.floor((a - b) / (7 * 24 * 60 * 60 * 1000));
}
