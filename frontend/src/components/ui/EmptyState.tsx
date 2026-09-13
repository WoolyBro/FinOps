import React from 'react';

type EmptyStateProps = {
  title: string;
  description: string;
  action?: React.ReactNode;
};

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  action,
}) => {
  return (
    <div className="py-[48px] px-6 text-center max-w-[500px] mx-auto">
      <div
        className="text-[14.5px] font-[600] mb-1.5"
        style={{ color: 'var(--ink)' }}
      >
        {title}
      </div>
      <div
        className="text-[13px] leading-relaxed mb-4"
        style={{ color: 'var(--ink-muted)' }}
      >
        {description}
      </div>
      {action && <div className="flex justify-center">{action}</div>}
    </div>
  );
};
