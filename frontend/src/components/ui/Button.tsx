import React from 'react';

export type ButtonVariant = 'default' | 'primary' | 'danger';

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  busy?: boolean;
  busyText?: string;
  icon?: React.ReactNode;
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'default',
  busy = false,
  busyText,
  disabled,
  icon,
  children,
  className = '',
  style,
  ...rest
}) => {
  const isDisabled = disabled || busy;

  // Base styles: 13px/550, 6px/12px padding, 6px radius, 120ms transition
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    fontSize: '13px',
    fontWeight: 550,
    lineHeight: '1.4',
    padding: '6px 12px',
    borderRadius: '6px',
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    opacity: isDisabled ? 0.5 : 1,
    whiteSpace: 'nowrap',
    transition: 'background-color 120ms ease, border-color 120ms ease, color 120ms ease, box-shadow 120ms ease',
    outline: 'none',
    textDecoration: 'none',
    ...style,
  };

  const variantStyles: Record<ButtonVariant, { normal: React.CSSProperties; hoverClass: string }> = {
    default: {
      normal: {
        backgroundColor: 'var(--surface)',
        border: '1px solid var(--line-strong)',
        color: 'var(--ink-body)',
        boxShadow: 'var(--shadow-xs)',
      },
      hoverClass: 'hover:bg-[var(--surface-sunken)]',
    },
    primary: {
      normal: {
        backgroundColor: 'var(--accent)',
        border: '1px solid var(--accent)',
        color: '#ffffff',
        boxShadow: 'var(--shadow-sm)',
      },
      hoverClass: 'hover:bg-[var(--accent-hover)] hover:border-[var(--accent-hover)]',
    },
    danger: {
      normal: {
        backgroundColor: 'var(--surface)',
        border: '1px solid var(--bad-ink)',
        color: 'var(--bad-ink)',
        boxShadow: 'var(--shadow-xs)',
      },
      hoverClass: 'hover:bg-[var(--bad-bg)]',
    },
  };

  const activeVariant = variantStyles[variant];

  return (
    <button
      disabled={isDisabled}
      className={`focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 ${!isDisabled ? activeVariant.hoverClass : ''} ${className}`}
      style={{ ...baseStyle, ...activeVariant.normal }}
      {...rest}
    >
      {icon && !busy && <span className="inline-flex items-center">{icon}</span>}
      <span>{busy && busyText ? busyText : children}</span>
    </button>
  );
};
