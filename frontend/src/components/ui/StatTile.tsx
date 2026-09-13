import React from 'react';

type StatTileProps = {
  label: string;
  value: string | React.ReactNode;
  subValue?: React.ReactNode;
  note?: React.ReactNode;
  isDanger?: boolean;
  className?: string;
  size?: 'normal' | 'loud';
  elevation?: 'none' | 'sm';
};

export const StatTile: React.FC<StatTileProps> = ({
  label,
  value,
  subValue,
  note,
  isDanger = false,
  className = '',
  size = 'normal',
  elevation = 'none',
}) => {
  const isLoud = size === 'loud';

  return (
    <div
      className={`rounded-[8px] border ${isLoud ? 'p-[18px] sm:p-[20px]' : 'p-[14px] sm:p-[16px]'} ${className}`}
      style={{
        backgroundColor: 'var(--surface)',
        borderColor: isDanger ? 'var(--bad-line)' : 'var(--line)',
        boxShadow: elevation === 'sm' ? 'var(--shadow-sm)' : 'none',
      }}
    >
      <div
        className="text-[12px] font-[550] mb-1.5"
        style={{ color: 'var(--ink-muted)' }}
      >
        {label}
      </div>
      <div className="flex flex-wrap items-baseline gap-2 mb-1">
        <div
          className={`${
            isLoud ? 'text-[28px] font-[600]' : 'text-[24px] font-[600]'
          } tabular-nums leading-none font-sans`}
          style={{ color: isDanger ? 'var(--bad-ink)' : 'var(--ink)' }}
        >
          {value}
        </div>
        {subValue && (
          <div className="text-[13px] font-[500] tabular-nums font-sans" style={{ color: 'var(--bad-ink)' }}>
            {subValue}
          </div>
        )}
      </div>
      {note && (
        <div
          className="text-[12px] leading-tight mt-1"
          style={{ color: 'var(--ink-faint)' }}
        >
          {note}
        </div>
      )}
    </div>
  );
};
