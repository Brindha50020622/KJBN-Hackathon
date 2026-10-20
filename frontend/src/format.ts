import type { DayRevenue } from "./api";

/** Paise (integer) to rupees text, Indian digit grouping. Integer maths only. */
export function formatRupees(paise: number): string {
  const abs = Math.abs(paise);
  const whole = Math.floor(abs / 100);
  const fraction = String(abs % 100).padStart(2, "0");
  const grouped = new Intl.NumberFormat("en-IN").format(whole);
  return `${paise < 0 ? "-" : ""}₹${grouped}.${fraction}`;
}

export function formatIstDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(iso));
}

/** Empty dates mean "no limit". ISO dates compare correctly as text. */
export function isRangeValid(from: string, to: string): boolean {
  return !from || !to || from <= to;
}

/** Adds a zero row for every day without sales. Input must be sorted by day. */
export function fillMissingDays(days: DayRevenue[]): DayRevenue[] {
  if (days.length === 0) return [];
  const byDay = new Map(days.map((d) => [d.day, d.revenue_paise]));
  const end = Date.parse(`${days[days.length - 1].day}T00:00:00Z`);
  const result: DayRevenue[] = [];
  for (let t = Date.parse(`${days[0].day}T00:00:00Z`); t <= end; t += 86_400_000) {
    const day = new Date(t).toISOString().slice(0, 10);
    result.push({ day, revenue_paise: byDay.get(day) ?? 0 });
  }
  return result;
}