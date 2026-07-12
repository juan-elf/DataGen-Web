/**
 * DataGen logo mark, taken verbatim from the design mockups in
 * "DataGen logo design/". Inherits text color via currentColor; the
 * arrow + output block stay accent-cyan as designed.
 */
export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <rect x="3" y="9" width="9" height="9" rx="1.5" fill="currentColor" />
      <rect x="3" y="30" width="9" height="9" rx="1.5" fill="currentColor" />
      <path d="M12 13.5 L15.5 24" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M12 34.5 L15.5 24" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      <rect
        x="18"
        y="18"
        width="12"
        height="12"
        rx="2"
        transform="rotate(45 24 24)"
        stroke="currentColor"
        strokeWidth="2.4"
        fill="none"
      />
      <path d="M32.5 24 L36 24" stroke="#22D3EE" strokeWidth="2.4" strokeLinecap="round" />
      <rect x="36" y="19.5" width="9" height="9" rx="1.5" fill="#22D3EE" />
    </svg>
  );
}

export function LogoWordmark({ iconSize = 26 }: { iconSize?: number }) {
  return (
    <span className="flex items-center gap-3 text-ink">
      <LogoMark size={iconSize} />
      <span className="font-bold tracking-tight" style={{ fontSize: iconSize * 0.65 }}>
        Data<span className="font-normal text-accent">Gen</span>
      </span>
    </span>
  );
}
