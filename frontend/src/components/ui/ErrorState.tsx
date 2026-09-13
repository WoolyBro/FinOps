import React from 'react';
import { Button } from './Button';

type ErrorStateProps = {
  error?: string;
  detail: string;
  onRetry?: () => void;
};

export const ErrorState: React.FC<ErrorStateProps> = ({
  error = 'Error',
  detail,
  onRetry,
}) => {
  return (
    <div
      className="rounded-[6px] border p-4 my-3 text-[13.5px]"
      style={{
        backgroundColor: 'var(--bad-bg)',
        borderColor: 'var(--bad-line)',
        color: 'var(--bad-ink)',
      }}
    >
      <div className="font-[600] mb-1">{error}</div>
      <div className="text-[13px] leading-relaxed mb-3">{detail}</div>
      {onRetry && (
        <Button variant="danger" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
};
