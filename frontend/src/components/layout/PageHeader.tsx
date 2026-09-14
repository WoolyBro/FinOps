import React from 'react';
import { ResetDemoButton } from './DemoReset';

type PageHeaderProps = {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
};

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  actions,
  className = '',
}) => {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-3 mb-4 ${className}`}>
      <div className="max-w-[62ch]">
        <h1
          className="text-[24px] font-[600] tracking-[-0.025em] leading-tight"
          style={{ color: 'var(--ink)' }}
        >
          {title}
        </h1>
        {/* A div, not a p: some pages pass block content (the client page's inline editors). */}
        {subtitle && (
          <div className="text-[13px] mt-1 leading-normal" style={{ color: 'var(--ink-muted)' }}>
            {subtitle}
          </div>
        )}
      </div>
      {/* Page actions first, then the demo reset in the far-right corner on every page. */}
      <div className="flex flex-wrap items-center gap-2 shrink-0 ml-auto">
        {actions}
        <ResetDemoButton />
      </div>
    </div>
  );
};
