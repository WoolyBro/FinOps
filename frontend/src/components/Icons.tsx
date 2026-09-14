import React from 'react';

type IconProps = {
  className?: string;
  size?: number;
};

export const IconOverview: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <rect x="2" y="2" width="5" height="5" rx="1" />
    <rect x="9" y="2" width="5" height="5" rx="1" />
    <rect x="2" y="9" width="5" height="5" rx="1" />
    <rect x="9" y="9" width="5" height="5" rx="1" />
  </svg>
);

export const IconAgent: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M2.5 3.5h11a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-7l-3 2v-2h-1a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1z" />
    <path d="M5.5 7h5" />
    <path d="M5.5 9h3" />
  </svg>
);

export const IconInvoices: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M3.5 1.5h6l3.5 3.5v9.5a1 1 0 0 1-1 1h-8.5a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1z" />
    <path d="M9.5 1.5v3.5h3.5" />
    <path d="M5.5 7.5h5" />
    <path d="M5.5 10.5h5" />
  </svg>
);

export const IconClients: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <circle cx="8" cy="4.5" r="2.5" />
    <path d="M3 13.5c0-2.5 2.2-4 5-4s5 1.5 5 4" />
  </svg>
);

export const IconPayments: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <rect x="2" y="3.5" width="12" height="9" rx="1" />
    <path d="M2 6.5h12" />
    <path d="M4.5 10h2.5" />
  </svg>
);

export const IconOverdue: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <circle cx="8" cy="8" r="6" />
    <path d="M8 4.5v3.8l2.5 1.5" />
  </svg>
);

export const IconReminders: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M2.5 4.5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1v-7z" />
    <path d="M2.5 5.5l5.5 3.5 5.5-3.5" />
  </svg>
);

export const IconReports: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M2.5 13.5h11" />
    <path d="M4.5 11.5v-4" />
    <path d="M8 11.5v-7" />
    <path d="M11.5 11.5v-9" />
  </svg>
);

export const IconCheck: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M3.5 8.5l3 3 6-6.5" />
  </svg>
);

export const IconCross: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M4 4l8 8" />
    <path d="M12 4l-8 8" />
  </svg>
);

export const IconSearch: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <circle cx="7" cy="7" r="4.5" />
    <path d="M10.5 10.5l3.5 3.5" />
  </svg>
);

export const IconPlus: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M8 3v10" />
    <path d="M3 8h10" />
  </svg>
);

export const IconChevronDown: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M4 6l4 4 4-4" />
  </svg>
);

export const IconChevronUp: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M4 10l4-4 4 4" />
  </svg>
);

export const IconChevronRight: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M6 4l4 4-4 4" />
  </svg>
);

export const IconArrowRight: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M3 8h10" />
    <path d="M9 4l4 4-4 4" />
  </svg>
);

export const IconPencil: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M10.5 2.5l3 3L4.5 14.5H1.5v-3l9-9z" />
  </svg>
);

export const IconDownload: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M8 2.5v8m0 0l-3-3m3 3l3-3" />
    <path d="M2.5 13.5h11" />
  </svg>
);

export const IconReset: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M2.75 8a5.25 5.25 0 1 0 1.54-3.71" />
    <path d="M2.5 2.5v2.75h2.75" />
  </svg>
);

export const IconCopy: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <rect x="5.5" y="5.5" width="8" height="8" rx="1" />
    <path d="M10.5 5.5v-2a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2" />
  </svg>
);

export const IconMenu: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M2.5 4h11" />
    <path d="M2.5 8h11" />
    <path d="M2.5 12h11" />
  </svg>
);
