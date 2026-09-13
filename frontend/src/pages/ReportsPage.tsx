import React, { useState, useEffect, useRef } from 'react';
import { api, totalMinor, totalText } from '../lib/api';
import { ApiError, ClientBreakdown, MonthlySeries, MonthPoint, Summary } from '../types';
import { PageHeader } from '../components/layout/PageHeader';
import { StatTile } from '../components/ui/StatTile';
import { Panel } from '../components/ui/Panel';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { ErrorState } from '../components/ui/ErrorState';
import { financialYearBounds, formatDateProse, monthBounds, quarterBounds, todayISO } from '../lib/format';

type ReportsPageProps = {
  onNavigate: (path: string) => void;
};

type PresetKey = 'this_month' | 'last_month' | 'this_quarter' | 'financial_year' | 'custom';

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function presetRange(preset: Exclude<PresetKey, 'custom'>): [string, string] {
  const today = todayISO();
  if (preset === 'this_month') return monthBounds(today);
  if (preset === 'last_month') return monthBounds(today, 1);
  if (preset === 'this_quarter') return quarterBounds(today);
  return financialYearBounds(today); // Indian financial year: April to March
}

// Plot geometry, in SVG units.
const PLOT_TOP = 36;
const PLOT_BOTTOM = 180;
const PLOT_HEIGHT = PLOT_BOTTOM - PLOT_TOP;

export const ReportsPage: React.FC<ReportsPageProps> = ({ onNavigate }) => {
  const [activePreset, setActivePreset] = useState<PresetKey>('financial_year');
  const [[startDate, endDate], setRange] = useState<[string, string]>(() => presetRange('financial_year'));

  const [summary, setSummary] = useState<Summary | null>(null);
  const [breakdown, setBreakdown] = useState<ClientBreakdown | null>(null);
  const [monthly, setMonthly] = useState<MonthlySeries | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<MonthPoint | null>(null);

  const chartRef = useRef<HTMLDivElement>(null);
  const hasChartAnimated = useRef(false);
  const [chartInView, setChartInView] = useState(false);
  const hasTableAnimated = useRef(false);

  const applyPreset = (preset: PresetKey) => {
    setActivePreset(preset);
    if (preset !== 'custom') setRange(presetRange(preset));
  };

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [sum, clients] = await Promise.all([
        api.getReportsSummary(startDate, endDate),
        api.getClientBreakdown(startDate, endDate),
      ]);
      setSummary(sum);
      setBreakdown(clients);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (startDate && endDate && startDate <= endDate) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate]);

  // The six-month chart does not depend on the selected range.
  useEffect(() => {
    api.getMonthly(6).then(setMonthly).catch((err) => setError(err as ApiError));
  }, []);

  useEffect(() => {
    if (breakdown) {
      const timer = window.setTimeout(() => (hasTableAnimated.current = true), 400);
      return () => window.clearTimeout(timer);
    }
  }, [breakdown]);

  useEffect(() => {
    if (!chartRef.current || hasChartAnimated.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          hasChartAnimated.current = true;
          setChartInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, [monthly]);

  const counts = summary?.invoice_counts_in_period ?? {};
  const liveIssued = summary?.invoices_issued_in_period ?? 0;
  const cancelled = summary?.cancelled_in_period ?? 0;
  const rangeInvalid = startDate > endDate;

  const scale = monthly?.scale_max_minor ?? 0;
  const barHeight = (minor: number) => (scale > 0 && minor > 0 ? Math.max(3, (minor / scale) * PLOT_HEIGHT) : 0);
  const firstMonth = monthly?.months[0];
  const lastMonth = monthly?.months[monthly.months.length - 1];

  return (
    <div className="space-y-3.5">
      <PageHeader title="Reports" subtitle="Invoiced against received, by month and by client." />

      <div
        className="flex flex-wrap items-center justify-between gap-3 p-2.5 rounded-[6px] border bg-[var(--surface)]"
        style={{ borderColor: 'var(--line)' }}
      >
        <div
          className="inline-flex p-0.5 rounded-[6px] border text-[12px] font-[500]"
          role="tablist"
          aria-label="Reporting period"
          style={{ backgroundColor: 'var(--surface-sunken)', borderColor: 'var(--line)' }}
        >
          {(
            [
              { id: 'this_month', label: 'This month' },
              { id: 'last_month', label: 'Last month' },
              { id: 'this_quarter', label: 'This quarter' },
              { id: 'financial_year', label: 'This financial year' },
              { id: 'custom', label: 'Custom' },
            ] as const
          ).map((preset) => {
            const active = activePreset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => applyPreset(preset.id)}
                className="px-2.5 py-1 rounded-[4px] transition-standard"
                style={{
                  backgroundColor: active ? 'var(--surface)' : 'transparent',
                  color: active ? 'var(--ink)' : 'var(--ink-muted)',
                  fontWeight: active ? 550 : 450,
                  boxShadow: active ? 'var(--shadow-xs)' : 'none',
                }}
              >
                {preset.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 text-[12px]">
          <label htmlFor="report-from" style={{ color: 'var(--ink-muted)' }}>
            From
          </label>
          <input
            id="report-from"
            type="date"
            className="px-2 py-1 border rounded-[4px] text-[12px] tabular-nums"
            style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--line)', color: 'var(--ink)' }}
            value={startDate}
            onChange={(e) => {
              setRange([e.target.value, endDate]);
              setActivePreset('custom');
            }}
          />
          <label htmlFor="report-to" style={{ color: 'var(--ink-muted)' }}>
            to
          </label>
          <input
            id="report-to"
            type="date"
            className="px-2 py-1 border rounded-[4px] text-[12px] tabular-nums"
            style={{ backgroundColor: 'var(--surface)', borderColor: rangeInvalid ? 'var(--bad-line)' : 'var(--line)', color: 'var(--ink)' }}
            value={endDate}
            onChange={(e) => {
              setRange([startDate, e.target.value]);
              setActivePreset('custom');
            }}
          />
        </div>
      </div>

      {rangeInvalid && (
        <div className="text-[12.5px]" style={{ color: 'var(--bad-ink)' }}>
          The end date is before the start date.
        </div>
      )}

      {error && <ErrorState error="Could not load the report" detail={error.detail} onRetry={load} />}

      {loading && !summary ? (
        <LoadingSkeleton message="Loading report…" rows={6} />
      ) : summary && breakdown ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <StatTile
              label="Invoiced in period"
              value={totalText(summary.invoiced_total)}
              note={
                cancelled > 0
                  ? `${plural(liveIssued, 'invoice')} · excludes ${cancelled} cancelled`
                  : plural(liveIssued, 'invoice')
              }
            />
            <StatTile
              label="Received in period"
              value={totalText(summary.received_total)}
              note={`across ${plural(summary.payments_in_period, 'payment')}`}
            />
            <StatTile
              label="Outstanding today"
              value={totalText(summary.outstanding_total)}
              note={`across ${plural(summary.open_invoice_count, 'open invoice')}`}
            />
            <StatTile
              label="Overdue today"
              value={totalText(summary.overdue_total)}
              note={
                summary.oldest_overdue
                  ? `oldest ${summary.oldest_overdue.days_overdue} days · ${summary.oldest_overdue.client_name}`
                  : 'nothing late'
              }
              isDanger={totalMinor(summary.overdue_total) > 0}
            />
          </div>

          <Panel
            elevation="sm"
            density="normal"
            title="Monthly billed vs received"
            subtitle={
              firstMonth && lastMonth
                ? `${firstMonth.name} – ${lastMonth.name}${
                    monthly?.other_currencies.length ? ` · ${monthly.currency} only` : ''
                  }`
                : undefined
            }
            actions={
              <div className="flex items-center gap-4 text-[12px]">
                <div className="flex items-center gap-1.5">
                  <span className="inline-block w-3 h-3 rounded-[2px]" style={{ backgroundColor: 'var(--line-strong)' }} />
                  <span style={{ color: 'var(--ink-muted)' }}>Invoiced</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="inline-block w-3 h-3 rounded-[2px]" style={{ backgroundColor: 'var(--accent)' }} />
                  <span style={{ color: 'var(--ink-muted)' }}>Received</span>
                </div>
              </div>
            }
          >
            <div ref={chartRef} className="relative pt-4 pb-2">
              {!monthly ? (
                <LoadingSkeleton message="Loading chart…" rows={3} />
              ) : scale === 0 ? (
                <div className="py-10 text-center text-[13px]" style={{ color: 'var(--ink-muted)' }}>
                  Nothing invoiced or received in the last six months.
                </div>
              ) : (
                <svg
                  viewBox="0 0 640 220"
                  className="w-full h-auto overflow-visible font-sans"
                  style={{ maxHeight: '240px' }}
                  role="img"
                  aria-label="Invoiced and received per month"
                >
                  {monthly.ticks.map((tick) => {
                    const y = PLOT_BOTTOM - (tick.minor / scale) * PLOT_HEIGHT;
                    return (
                      <g key={tick.minor}>
                        <line
                          x1="48"
                          y1={y}
                          x2="620"
                          y2={y}
                          stroke={tick.minor === 0 ? 'var(--line-strong)' : 'var(--line)'}
                          strokeWidth="1"
                          strokeDasharray={tick.minor === 0 ? undefined : '3 3'}
                        />
                        <text x="40" y={y + 4} textAnchor="end" fontSize="10" fill="var(--ink-faint)" className="tabular-nums font-mono">
                          {tick.display}
                        </text>
                      </g>
                    );
                  })}

                  {monthly.months.map((d, index) => {
                    const groupWidth = 570 / monthly.months.length;
                    const groupX = 50 + index * groupWidth;
                    const invHeight = barHeight(d.invoiced_minor);
                    const payHeight = barHeight(d.received_minor);
                    const barWidth = 18;
                    const isEmpty = d.invoiced_minor === 0 && d.received_minor === 0;

                    return (
                      <g
                        key={d.month}
                        onMouseEnter={() => setHovered(d)}
                        onMouseLeave={() => setHovered(null)}
                        className="cursor-default"
                      >
                        {/* Full-height hit area so hovering a short bar still works */}
                        <rect x={groupX} y={PLOT_TOP} width={groupWidth} height={PLOT_HEIGHT} fill="transparent" />
                        {invHeight > 0 && (
                          <rect
                            x={groupX + groupWidth / 2 - barWidth - 2}
                            y={PLOT_BOTTOM - invHeight}
                            width={barWidth}
                            height={invHeight}
                            rx="2"
                            fill="var(--line-strong)"
                            className={chartInView ? 'chart-bar-grow' : ''}
                            style={{ animationDelay: `${index * 40}ms` }}
                          />
                        )}
                        {payHeight > 0 && (
                          <rect
                            x={groupX + groupWidth / 2 + 2}
                            y={PLOT_BOTTOM - payHeight}
                            width={barWidth}
                            height={payHeight}
                            rx="2"
                            fill="var(--accent)"
                            className={chartInView ? 'chart-bar-grow' : ''}
                            style={{ animationDelay: `${index * 40}ms` }}
                          />
                        )}
                        <text
                          x={groupX + groupWidth / 2}
                          y="200"
                          textAnchor="middle"
                          fontSize="11"
                          fill={isEmpty ? 'var(--ink-faint)' : 'var(--ink-muted)'}
                        >
                          {d.label}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}

              {hovered && (
                <div
                  className="absolute p-2.5 rounded-[6px] border text-[12px] pointer-events-none z-20"
                  style={{
                    backgroundColor: 'var(--surface)',
                    borderColor: 'var(--line)',
                    boxShadow: 'var(--shadow-md)',
                    left: '50%',
                    top: '8px',
                    transform: 'translateX(-50%)',
                  }}
                >
                  <div className="font-[500] mb-1 text-[12.5px]" style={{ color: 'var(--ink)' }}>
                    {hovered.name}
                  </div>
                  <div className="space-y-0.5 tabular-nums">
                    <div className="flex justify-between gap-4">
                      <span style={{ color: 'var(--ink-muted)' }}>Invoiced</span>
                      <span className="font-[500] font-mono">{hovered.invoiced_display}</span>
                    </div>
                    <div className="flex justify-between gap-4">
                      <span style={{ color: 'var(--ink-muted)' }}>Received</span>
                      <span className="font-[500] font-mono" style={{ color: 'var(--accent-ink)' }}>
                        {hovered.received_display}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Panel>

          <Panel
            elevation="none"
            density="dense"
            title="Breakdown by client"
            subtitle={`Invoiced and received ${formatDateProse(startDate)} – ${formatDateProse(endDate)}; outstanding as of today`}
            noPadding
          >
            {breakdown.clients.length === 0 ? (
              <div className="p-8 text-center text-[13px]" style={{ color: 'var(--ink-muted)' }}>
                No clients on file yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse table-fixed min-w-[650px] text-[13px]">
                  <thead style={{ backgroundColor: 'var(--surface-sunken)', borderBottom: '1px solid var(--line)' }}>
                    <tr className="text-[11px] uppercase font-[550] tracking-[0.05em]" style={{ color: 'var(--ink-muted)' }}>
                      <th scope="col" className="py-2.5 px-3.5 text-left">Client</th>
                      <th scope="col" style={{ width: '140px' }} className="py-2.5 px-3.5 text-right">Invoiced</th>
                      <th scope="col" style={{ width: '140px' }} className="py-2.5 px-3.5 text-right">Received</th>
                      <th scope="col" style={{ width: '150px' }} className="py-2.5 px-3.5 text-right">Outstanding</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: 'var(--line)' }}>
                    {breakdown.clients.map((c, idx) => {
                      const animate = !hasTableAnimated.current;
                      const owes = totalMinor(c.outstanding_total) > 0;
                      return (
                        <tr
                          key={c.client_id}
                          className={`table-row ${animate ? 'table-row-enter' : ''}`}
                          style={animate ? { animationDelay: `${Math.min(idx, 10) * 24}ms` } : undefined}
                        >
                          <td className="py-2 px-3.5 font-[500] text-left truncate">
                            <button
                              type="button"
                              onClick={() => onNavigate(`/clients/${c.client_id}`)}
                              className="hover:underline text-left"
                              style={{ color: 'var(--ink)' }}
                            >
                              {c.name}
                            </button>
                          </td>
                          <td className="py-2 px-3.5 text-right font-mono tabular-nums" style={{ color: 'var(--ink-muted)' }}>
                            {totalText(c.invoiced_total)}
                          </td>
                          <td className="py-2 px-3.5 text-right font-mono tabular-nums" style={{ color: 'var(--ok-ink)' }}>
                            {totalText(c.received_total)}
                          </td>
                          <td
                            className="py-2 px-3.5 text-right font-mono font-[500] tabular-nums"
                            style={{ color: owes ? 'var(--bad-ink)' : 'var(--ink)' }}
                          >
                            {totalText(c.outstanding_total)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel
            elevation="none"
            density="dense"
            title="Invoices issued in period"
            subtitle={`${plural(liveIssued + cancelled, 'invoice')} issued${cancelled ? `, ${cancelled} since cancelled` : ''}`}
          >
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-left">
              {(
                [
                  ['Paid', counts['PAID'] ?? 0, 'var(--ok-ink)'],
                  ['Partially paid', counts['PARTIALLY_PAID'] ?? 0, 'var(--warn-ink)'],
                  ['Unpaid', counts['UNPAID'] ?? 0, 'var(--ink)'],
                  ['Cancelled', cancelled, 'var(--ink-muted)'],
                ] as const
              ).map(([name, value, color]) => (
                <div key={name} className="p-3 rounded-[6px] border bg-[var(--surface)]" style={{ borderColor: 'var(--line)' }}>
                  <div className="text-[10.5px] font-[550] uppercase tracking-[0.05em]" style={{ color: 'var(--ink-faint)' }}>
                    {name}
                  </div>
                  <div className="text-[18px] font-[500] mt-1 tabular-nums" style={{ color }}>
                    {value}
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-2.5 mt-3 border-t text-[12.5px] flex items-center gap-1.5" style={{ borderColor: 'var(--line)', color: 'var(--ink-muted)' }}>
              <span className="font-[600] font-mono tabular-nums" style={{ color: summary.overdue_in_period ? 'var(--bad-ink)' : 'var(--ink)' }}>
                {summary.overdue_in_period}
              </span>
              <span>of these {summary.overdue_in_period === 1 ? 'is' : 'are'} overdue today</span>
            </div>
          </Panel>
        </>
      ) : null}
    </div>
  );
};
