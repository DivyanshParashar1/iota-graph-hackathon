// Inline icons (24x24, 1.6 stroke, round caps). Each is a list of SVG path strings so the same glyph can be
// drawn as an <svg> in the DOM and as a Path2D on the graph canvas. No icon font, no dependency.

export const ICONS: Record<string, string[]> = {
  // domain glyphs, picked for an object type by its display.icon hint or its label
  cube: ["M12 2.8 20.5 7.5v9L12 21.2 3.5 16.5v-9z", "M3.5 7.5 12 12.2l8.5-4.7", "M12 12.2v9"],
  globe: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M3 12h18", "M12 3c2.6 2.6 3.8 5.6 3.8 9s-1.2 6.4-3.8 9c-2.6-2.6-3.8-5.6-3.8-9S9.4 5.6 12 3z"],
  building: ["M4 21V5l8-2v18", "M12 8h8v13", "M2.5 21h19", "M7 8h2", "M7 12h2", "M7 16h2", "M15 12h2", "M15 16h2"],
  factory: ["M3 21V10l5 3V10l5 3V10l5 3V4h3v17z", "M2 21h20", "M7 17h2", "M12 17h2", "M17 17h2"],
  warehouse: ["M3 21V9l9-5 9 5v12", "M7 21v-8h10v8", "M7 17h10", "M2 21h20"],
  truck: ["M2 6h11v10H2z", "M13 9h4.5l3.5 3.5V16h-8", "M6 18.5a1.8 1.8 0 1 0 0 .01", "M17 18.5a1.8 1.8 0 1 0 0 .01"],
  ship: ["M3 15l1.8 5h14.4l1.8-5-9-3z", "M6 13.3V8h12v5.3", "M12 3v5", "M9.5 5h5"],
  plane: ["M2.5 13.5 21 6.5l-3 13-5.5-4-3 4v-5.5z", "M12.5 15.5 21 6.5"],
  package: ["M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5z", "M3.5 7.5 12 12l8.5-4.5", "M12 12v9", "M7.8 5.3l8.5 4.5"],
  box: ["M3 8h18v12H3z", "M2 4h20v4H2z", "M10 12h4"],
  leaf: ["M5 19c0-8 5-13 15-14-1 10-6 15-14 15", "M5 19c3-4 6-7 10-9"],
  gear: ["M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z", "M12 2.5v3", "M12 18.5v3", "M2.5 12h3", "M18.5 12h3", "M5.3 5.3l2.1 2.1", "M16.6 16.6l2.1 2.1", "M5.3 18.7l2.1-2.1", "M16.6 7.4l2.1-2.1"],
  shoe: ["M2.5 17.5V9l4 1.5 2-3 3.5 3c2.5 1 6 1.5 8 3.5 1 1 1.5 2.5 1.5 3.5z", "M2.5 17.5h19", "M9 11l1 1.5", "M11.5 12.5l1 1.5"],
  user: ["M12 3.5a4 4 0 1 0 0 8a4 4 0 1 0 0-8z", "M4 20.5c1-4 4.2-6 8-6s7 2 8 6"],
  users: ["M9 4a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7z", "M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5", "M16 4.4a3.5 3.5 0 0 1 0 6.2", "M18 14.8c1.8.7 3 2.4 3.5 5.2"],
  store: ["M3 9l1.5-5h15L21 9", "M3 9h18v2.5a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0z", "M4.5 13v8h15v-8", "M10 21v-5h4v5"],
  coin: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M15 9c-.5-1-1.6-1.5-3-1.5-1.8 0-3 .9-3 2.2 0 3 6 1.6 6 4.6 0 1.3-1.3 2.2-3 2.2-1.5 0-2.6-.6-3.1-1.6", "M12 6v1.5", "M12 16.5V18"],
  document: ["M6 2.5h8l5 5v14H6z", "M14 2.5v5h5", "M9 12.5h7", "M9 16h7"],
  pin: ["M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z", "M12 7a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5z"],
  calendar: ["M3.5 5.5h17v15h-17z", "M3.5 10h17", "M8 3v4", "M16 3v4"],
  alert: ["M12 3.5 21.5 20h-19z", "M12 10v4.5", "M12 17.3v.2"],
  bolt: ["M13 2.5 4.5 13.5H12l-1 8 8.5-11H12z"],
  route: ["M6 19a2 2 0 1 0 0 .01", "M18 5a2 2 0 1 0 0 .01", "M6 17V9.5A3.5 3.5 0 0 1 9.5 6h3", "M18 7v7.5a3.5 3.5 0 0 1-3.5 3.5h-3"],
  // interface glyphs
  search: ["M10.5 4a6.5 6.5 0 1 0 0 13a6.5 6.5 0 1 0 0-13z", "M15.5 15.5 21 21"],
  graph: ["M6 6a2.2 2.2 0 1 0 0 .01", "M18 7a2.2 2.2 0 1 0 0 .01", "M12 18a2.2 2.2 0 1 0 0 .01", "M8 6.4l8 .5", "M7 8l4 8", "M17 9l-4 7"],
  schema: ["M3 4h7v5H3z", "M14 4h7v5h-7z", "M8.5 15h7v5h-7z", "M6.5 9v3h11V9", "M12 12v3"],
  table: ["M3 4.5h18v15H3z", "M3 9.5h18", "M3 14.5h18", "M9 4.5v15"],
  list: ["M8 6h13", "M8 12h13", "M8 18h13", "M3.5 6h.5", "M3.5 12h.5", "M3.5 18h.5"],
  chat: ["M4 4.5h16v11H9l-5 4z", "M8 9h8", "M8 12h5"],
  experts: ["M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z"],
  incident: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M12 7.5v5.5", "M12 16.3v.2"],
  chevronRight: ["M9 5l7 7-7 7"],
  chevronDown: ["M5 9l7 7 7-7"],
  chevronLeft: ["M15 5l-7 7 7 7"],
  arrowRight: ["M4 12h15", "M13 6l6 6-6 6"],
  close: ["M6 6l12 12", "M18 6 6 18"],
  check: ["M4.5 12.5l5 5L19.5 7"],
  external: ["M14 4h6v6", "M20 4l-9 9", "M18 14v6H4V6h6"],
  fit: ["M4 9V4h5", "M15 4h5v5", "M20 15v5h-5", "M9 20H4v-5"],
  tag: ["M3 3h8l10 10-8 8L3 11z", "M7.5 7.5h.01"],
  key: ["M8 10a4.5 4.5 0 1 0 0 9a4.5 4.5 0 1 0 0-9z", "M11.2 11.3 20 2.5", "M16.5 6l2.5 2.5", "M14 8.5l2 2"],
  link: ["M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2", "M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"],
  info: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M12 11v5.5", "M12 7.7v.2"],
  sparkle: ["M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z", "M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"],
  menu: ["M3.5 6h17", "M3.5 12h17", "M3.5 18h17"],
  layers: ["M12 3 2.5 8 12 13l9.5-5z", "M2.5 12.5 12 17.5l9.5-5", "M2.5 16.5 12 21.5l9.5-5"],
  eye: ["M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z", "M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z"],
  play: ["M7 4.5v15l12-7.5z"],
  refresh: ["M20 11a8 8 0 1 0-2.3 5.7", "M20 4v7h-7"],
  database: ["M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3z", "M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6", "M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"],
};

// Keywords in an icon hint or a type label -> glyph. The ontology agent writes free-text icon hints, so this is
// matched loosely; anything unrecognised falls back to a cube.
const KEYWORDS: [RegExp, string][] = [
  [/region|country|geo|globe|market|zone|area|location/i, "globe"],
  [/factory|plant|mill|manufactur|assembl|site|atelier|workshop/i, "factory"],
  [/warehouse|distribution|\bdc\b|depot|hub|fulfil|storage|inventory/i, "warehouse"],
  [/carrier|truck|haul|freight|logistic|transport|lane/i, "truck"],
  [/vessel|ship(?!ment)|ocean|port|sea/i, "ship"],
  [/air|flight|plane/i, "plane"],
  [/shipment|parcel|package|order|consignment|delivery|po\b|purchase/i, "package"],
  [/supplier|vendor|company|organi|partner|manufacturer|building/i, "building"],
  [/material|raw|leaf|ingredient|commodity|bean|crop|coffee|cotton/i, "leaf"],
  [/component|part|sku|bom|gear|assembly|module/i, "gear"],
  [/product|shoe|style|item|good|article|finished/i, "shoe"],
  [/customer|client|account|buyer|consumer|user|person|contact/i, "user"],
  [/team|employee|staff|people|worker/i, "users"],
  [/store|shop|retail|outlet/i, "store"],
  [/price|cost|invoice|payment|contract|money|coin|spend/i, "coin"],
  [/document|certificate|cert|doc|policy|regulation/i, "document"],
  [/event|incident|risk|alert|disruption|issue/i, "alert"],
  [/route|path/i, "route"],
  [/date|calendar|season|period|week/i, "calendar"],
  [/box|pack|container|pallet/i, "box"],
  [/energy|power/i, "bolt"],
];

export function iconFor(hint = "", label = ""): string {
  if (hint && ICONS[hint]) return hint;
  for (const s of [hint, label]) {
    if (!s) continue;
    for (const [re, name] of KEYWORDS) if (re.test(s)) return name;
  }
  return "cube";
}

export function Icon({ name, size = 16, className = "", strokeWidth = 1.6, title }: {
  name: string;
  size?: number;
  className?: string;
  strokeWidth?: number;
  title?: string;
}) {
  const paths = ICONS[name] ?? ICONS.cube;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
    >
      {title && <title>{title}</title>}
      {paths.map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  );
}

const path2d = new Map<string, Path2D[]>();

/** Draw an icon centred at (x, y) on a canvas, `size` units wide, stroked in `color`. */
export function drawIcon(ctx: CanvasRenderingContext2D, name: string, x: number, y: number, size: number,
                         color: string, lineWidth = 1.8) {
  let ps = path2d.get(name);
  if (!ps) {
    ps = (ICONS[name] ?? ICONS.cube).map((d) => new Path2D(d));
    path2d.set(name, ps);
  }
  const k = size / 24;
  ctx.save();
  ctx.translate(x - size / 2, y - size / 2);
  ctx.scale(k, k);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const p of ps) ctx.stroke(p);
  ctx.restore();
}
