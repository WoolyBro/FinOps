import React from 'react';
import { InvoiceStatus, ReminderStatus } from '../../types';

export type BadgeVariant =
  | 'ok'
  | 'warn'
  | 'bad'
  | 'neutral'
  | 'cancelled';

type BadgeProps = {
  variant?: BadgeVariant;
  status?: InvoiceStatus | ReminderStatus | 'OVERDUE' | string;
  daysOverdue?: number;
  children?: React.ReactNode;
  className?: string;
};

export const Badge: React.FC<BadgeProps> = ({
  variant,
  status,
  daysOverdue,
  children,
  className = '',
}) => {
  // Derive variant and text if status is provided
  let computedVariant: BadgeVariant = variant || 'neutral';
  let displayText = children;

  if (status) {
    switch (status) {
      case 'PAID':
      case 'APPROVED':
        computedVariant = 'ok';
        displayText = displayText || (status === 'PAID' ? 'Paid' : 'Approved');
        break;
      case 'PARTIALLY_PAID':
        computedVariant = 'warn';
        displayText = displayText || 'Partially paid';
        break;
      case 'DRAFT':
        computedVariant = 'warn';
        displayText = displayText || 'Draft';
        break;
      case 'UNPAID':
        computedVariant = 'neutral';
        displayText = displayText || 'Unpaid';
        break;
      case 'SENT':
        computedVariant = 'neutral';
        displayText = displayText || 'Sent';
        break;
      case 'CANCELLED':
        computedVariant = 'cancelled';
        displayText = displayText || 'Cancelled';
        break;
      case 'OVERDUE':
        computedVariant = 'bad';
        displayText = displayText || (daysOverdue ? `${daysOverdue}d overdue` : 'Overdue');
        break;
    }
  }

  if (daysOverdue !== undefined && daysOverdue > 0 && !displayText) {
    computedVariant = 'bad';
    displayText = `${daysOverdue}d overdue`;
  }

  // Exact styles per spec: 11.5px/600, 2px/8px padding, 6px radius
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    fontSize: '11.5px',
    fontWeight: 600,
    lineHeight: '1.2',
    padding: '2px 8px',
    borderRadius: '6px',
    whiteSpace: 'nowrap',
  };

  const variantStyles: Record<BadgeVariant, React.CSSProperties> = {
    ok: {
      backgroundColor: 'var(--ok-bg)',
      color: 'var(--ok-ink)',
    },
    warn: {
      backgroundColor: 'var(--warn-bg)',
      color: 'var(--warn-ink)',
    },
    bad: {
      backgroundColor: 'var(--bad-bg)',
      color: 'var(--bad-ink)',
    },
    neutral: {
      backgroundColor: 'var(--neutral-bg)',
      color: 'var(--neutral-ink)',
    },
    cancelled: {
      backgroundColor: 'var(--neutral-bg)',
      color: 'var(--neutral-ink)',
      textDecoration: 'line-through',
    },
  };

  return (
    <span
      className={className}
      style={{ ...baseStyle, ...variantStyles[computedVariant] }}
    >
      {displayText}
    </span>
  );
};
