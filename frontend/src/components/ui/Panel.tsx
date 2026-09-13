import React from 'react';

type PanelProps = {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  noPadding?: boolean;
  elevation?: 'none' | 'sm';
  density?: 'dense' | 'normal' | 'spacious' | 'sidebar';
};

export const Panel: React.FC<PanelProps> = ({
  title,
  subtitle,
  actions,
  children,
  className = '',
  bodyClassName = '',
  noPadding = false,
  elevation = 'none',
  density = 'normal',
}) => {
  const hasHeader = title || subtitle || actions;

  const headerPadding = density === 'sidebar'
    ? '10px 14px'
    : density === 'dense'
    ? '10px 14px'
    : density === 'spacious'
    ? '16px 20px'
    : '12px 18px';

  const bodyPadding = noPadding
    ? ''
    : density === 'sidebar'
    ? 'p-[12px]'
    : density === 'dense'
    ? 'p-[12px]'
    : density === 'spacious'
    ? 'p-[20px] sm:p-[24px]'
    : 'p-[16px] sm:p-[18px]';

  return (
    <div
      className={`rounded-[8px] border overflow-hidden ${className}`}
      style={{
        backgroundColor: 'var(--surface)',
        borderColor: 'var(--line)',
        boxShadow: elevation === 'sm' ? 'var(--shadow-sm)' : 'none',
        contain: 'layout paint',
      }}
    >
      {hasHeader && (
        <div
          className="flex items-center justify-between border-b"
          style={{
            padding: headerPadding,
            borderColor: 'var(--line)',
          }}
        >
          <div className="min-w-0 pr-2">
            {title && (
              <div
                className="text-[14px] font-[600] truncate"
                style={{ color: 'var(--ink)' }}
              >
                {title}
              </div>
            )}
            {subtitle && (
              <div
                className="text-[12px] mt-0.5"
                style={{ color: 'var(--ink-muted)' }}
              >
                {subtitle}
              </div>
            )}
          </div>
          {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
        </div>
      )}
      <div className={`${bodyPadding} ${bodyClassName}`}>
        {children}
      </div>
    </div>
  );
};
