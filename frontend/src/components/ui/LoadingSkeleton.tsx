import React from 'react';

type LoadingSkeletonProps = {
  message?: string;
  rows?: number;
  rowHeight?: number;
};

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  message = 'Loading…',
  rows = 4,
  rowHeight = 44,
}) => {
  return (
    <div className="w-full py-2">
      {message && (
        <div
          className="text-[13px] italic mb-3 px-4"
          style={{ color: 'var(--ink-muted)' }}
        >
          {message}
        </div>
      )}
      <div className="space-y-1">
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            className="w-full rounded-[4px] skeleton-breathe"
            style={{
              height: `${rowHeight}px`,
              backgroundColor: 'var(--surface-sunken)',
              borderBottom: '1px solid var(--line)',
            }}
          />
        ))}
      </div>
    </div>
  );
};
