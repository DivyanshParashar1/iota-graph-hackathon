import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ElementType, ReactNode, RefObject } from "react";

// The handful of motion primitives the landing page needs, without an animation library: scroll progress through
// an element, an in-view flag, and a reveal wrapper. The transitions themselves live in index.css (.reveal).

/** True while the element is inside the viewport (shrunk by `margin`); with `once`, stays true after the first time. */
export function useInView<T extends Element>(ref: RefObject<T | null>, { once = true, margin = "0px" } = {}) {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setInView(true);
          if (once) io.disconnect();
        } else if (!once) setInView(false);
      },
      { rootMargin: margin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, once, margin]);
  return inView;
}

/** Window scroll progress (0..1) of an element, from when its top reaches `startAt` of the viewport height to when
 *  its bottom reaches `endAt`. `startAt: 0, endAt: 1` with a sticky child gives framer's "start start"/"end end". */
export function useScrollProgress<T extends HTMLElement>(ref: RefObject<T | null>, startAt = 0, endAt = 1) {
  const [p, setP] = useState(0);
  const [scrolled, setScrolled] = useState(0);
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      raf = 0;
      setScrolled(window.scrollY);
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const span = r.height + (startAt - endAt) * vh;
      setP(span <= 0 ? 0 : Math.max(0, Math.min(1, (startAt * vh - r.top) / span)));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [ref, startAt, endAt]);
  return { progress: p, scrollY: scrolled };
}

/** Map `v` from [a, b] onto [c, d], clamped. */
export const mapRange = (v: number, a: number, b: number, c: number, d: number) =>
  c + (d - c) * Math.max(0, Math.min(1, (v - a) / (b - a)));

/** Fades and slides its children in the first time they scroll into view. */
export function Reveal({ children, as: Tag = "div", delay = 0, from = "translateY(28px)", margin = "0px 0px -8% 0px",
  className = "", style }: {
  children?: ReactNode; as?: ElementType; delay?: number; from?: string; margin?: string; className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { margin });
  return (
    <Tag
      ref={ref}
      className={`reveal ${inView ? "in" : ""} ${className}`}
      style={{ ...style, "--reveal-delay": `${delay}s`, "--reveal-from": from } as CSSProperties}
    >
      {children}
    </Tag>
  );
}
