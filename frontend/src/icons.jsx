function Svg({ children, size = 20, className = "", ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function ShieldCheckIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
      <path d="M9 12.5l2 2 4-4.5" />
    </Svg>
  );
}

export function AlertTriangleIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 4l9.5 16H2.5L12 4z" />
      <path d="M12 10v4" />
      <path d="M12 17.5v.1" />
    </Svg>
  );
}

export function UploadCloudIcon(props) {
  return (
    <Svg {...props}>
      <path d="M7 17.5a4.5 4.5 0 0 1-.7-8.94 5.5 5.5 0 0 1 10.6-1.9A4.5 4.5 0 0 1 17 17.5" />
      <path d="M12 12v7" />
      <path d="M9 15l3-3 3 3" />
    </Svg>
  );
}

export function SpinnerIcon(props) {
  return (
    <Svg {...props} className={`icon-spin ${props.className ?? ""}`}>
      <path d="M12 3a9 9 0 1 0 9 9" />
    </Svg>
  );
}

export function DownloadIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 4v11" />
      <path d="M8 11l4 4 4-4" />
      <path d="M5 19.5h14" />
    </Svg>
  );
}

export function RefreshIcon(props) {
  return (
    <Svg {...props}>
      <path d="M4 12a8 8 0 0 1 13.66-5.66L20 8" />
      <path d="M20 4v4h-4" />
      <path d="M20 12a8 8 0 0 1-13.66 5.66L4 16" />
      <path d="M4 20v-4h4" />
    </Svg>
  );
}

export function LockIcon(props) {
  return (
    <Svg {...props}>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </Svg>
  );
}

export function ImageIcon(props) {
  return (
    <Svg {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.5" />
      <path d="M21 16l-5.5-5.5L4 21" />
    </Svg>
  );
}
