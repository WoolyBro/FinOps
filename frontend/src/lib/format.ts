// Date formatting only. Money is never formatted here: every amount arrives
// from the server as a *_display string and is rendered exactly as sent.

const MONTHS_LONG = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Today in the browser's local calendar, as YYYY-MM-DD. */
export function todayISO(): string {
  const now = new Date();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${mm}-${dd}`;
}

function parts(dateStr: string): [number, number, number] | null {
  const bits = dateStr.slice(0, 10).split('-');
  if (bits.length !== 3) return null;
  const [y, m, d] = bits.map((b) => parseInt(b, 10));
  return Number.isNaN(y) || Number.isNaN(m) || Number.isNaN(d) ? null : [y, m, d];
}

/** "18 August 2026" */
export function formatDateProse(dateStr: string | null): string {
  if (!dateStr) return '—';
  const p = parts(dateStr);
  return p ? `${p[2]} ${MONTHS_LONG[p[1] - 1]} ${p[0]}` : dateStr;
}

/** "18 Aug 2026" */
export function formatDateTable(dateStr: string | null): string {
  if (!dateStr) return '—';
  const p = parts(dateStr);
  return p ? `${p[2]} ${MONTHS_SHORT[p[1] - 1]} ${p[0]}` : dateStr;
}

/**
 * "Today", "Yesterday", then a plain date — relative time stops being useful
 * after two days. Ledger events are dated, not timed, so no clock time is
 * shown: inventing one would put a fact on screen the ledger does not hold.
 */
export function formatRelative(dateStr: string, base = todayISO()): string {
  if (!dateStr) return '—';
  const item = parts(dateStr);
  const ref = parts(base);
  if (!item || !ref) return dateStr;

  const diffDays = Math.round(
    (Date.UTC(ref[0], ref[1] - 1, ref[2]) - Date.UTC(item[0], item[1] - 1, item[2])) / 86_400_000,
  );
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (item[0] === ref[0]) return `${item[2]} ${MONTHS_LONG[item[1] - 1]}`;
  return `${item[2]} ${MONTHS_LONG[item[1] - 1]} ${item[0]}`;
}

/** First and last day of the month containing `iso`, offset by `back` months. */
export function monthBounds(iso: string, back = 0): [string, string] {
  const p = parts(iso)!;
  const index = p[0] * 12 + (p[1] - 1) - back;
  const y = Math.floor(index / 12);
  const m = (index % 12) + 1;
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const mm = String(m).padStart(2, '0');
  return [`${y}-${mm}-01`, `${y}-${mm}-${String(last).padStart(2, '0')}`];
}

/** Indian financial year (April–March) containing `iso`. */
export function financialYearBounds(iso: string): [string, string] {
  const p = parts(iso)!;
  const startYear = p[1] >= 4 ? p[0] : p[0] - 1;
  return [`${startYear}-04-01`, `${startYear + 1}-03-31`];
}

/** The calendar quarter of the Indian financial year containing `iso`. */
export function quarterBounds(iso: string): [string, string] {
  const p = parts(iso)!;
  const firstMonth = Math.floor((p[1] - 1) / 3) * 3 + 1;
  const endMonth = firstMonth + 2;
  const last = new Date(Date.UTC(p[0], endMonth, 0)).getUTCDate();
  const pad = (n: number) => String(n).padStart(2, '0');
  return [`${p[0]}-${pad(firstMonth)}-01`, `${p[0]}-${pad(endMonth)}-${pad(last)}`];
}
