"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Scroll-reveal wrapper matching the landing mockup's IntersectionObserver
 * fade-up behavior. Content is visible without JS (no opacity:0 default);
 * the animation only plays once when the block first enters the viewport.
 */
export function Reveal({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setInView(true);
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={`${inView ? "dg-in" : ""} ${className}`}>
      {children}
    </div>
  );
}
