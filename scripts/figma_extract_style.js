// READ-ONLY Figma style extractor for the visual-parity harness (`marketing` suite).
//
// Paste into a `use_figma` call (Figma MCP) with the frame's node id substituted for
// NODE_ID below. It writes NOTHING to the file: it walks one frame and returns a compact JSON
// description of every visible text node and every box that paints something, in coordinates
// relative to the frame, so `scripts/vp_style_diff.py` can compare Figma's values with the
// built page's computed styles (type size, weight, line height, colour, position, radius, gap).
//
// Save the returned JSON as `docs/design/visual-parity/marketing/figma-style/<slug>.json`
// and register it with:
//     python3 scripts/vp_reference.py --suite marketing style --slug <slug> --file <that file>
//
// Why a script and not `get_design_context`: that tool returns generated React/Tailwind for a
// human to adapt; this returns the raw numbers, which is what a repeatable comparison needs.
// Both are fine for reading a design; only this one can be diffed by a program.
//
// Colours are the RESOLVED paint (a variable-bound fill still reports its resolved colour).
// Weights are derived from the Inter style name. Mixed-style text reports its first segment.

const NODE_ID = "__NODE_ID__";
const root = await figma.getNodeByIdAsync(NODE_ID);
if (!root || !root.absoluteBoundingBox) return { error: "node not found or has no bounds: " + NODE_ID };
const rb = root.absoluteBoundingBox;
const r1 = (n) => Math.round(n * 10) / 10;
const hx = (c) => "#" + [c.r, c.g, c.b].map((v) => Math.round(v * 255).toString(16).padStart(2, "0")).join("");
const WEIGHTS = { thin: 100, extralight: 200, "extra light": 200, light: 300, regular: 400, medium: 500,
  semibold: 600, "semi bold": 600, bold: 700, extrabold: 800, "extra bold": 800, black: 900 };
const weightOf = (style) => {
  const k = String(style || "").toLowerCase().replace(/italic/g, "").trim();
  return WEIGHTS[k] || 400;
};
const paint = (arr) => {
  if (!arr || arr === figma.mixed) return null;
  const vis = arr.filter((p) => p.visible !== false);
  const s = vis.find((p) => p.type === "SOLID");
  if (s) return hx(s.color) + (s.opacity !== undefined && s.opacity < 1 ? "@" + r1(s.opacity) : "");
  const g = vis.find((p) => String(p.type).startsWith("GRADIENT"));
  if (g) return "grad:" + g.gradientStops.map((st) => hx(st.color)).join(">");
  if (vis.find((p) => p.type === "IMAGE")) return "image";
  return null;
};
const texts = [];
const boxes = [];
const MAX = 1500;
const rel = (n) => {
  const b = n.absoluteBoundingBox;
  if (!b) return null;
  return { x: r1(b.x - rb.x), y: r1(b.y - rb.y), w: r1(b.width), h: r1(b.height) };
};
const walk = (n) => {
  if (n.visible === false) return;
  if (texts.length + boxes.length > MAX) return;
  if (n.type === "TEXT") {
    const b = rel(n);
    if (!b) return;
    let fs = n.fontSize, fn = n.fontName, ls = n.letterSpacing, lh = n.lineHeight, fills = n.fills;
    if (fs === figma.mixed || fn === figma.mixed || ls === figma.mixed || lh === figma.mixed || fills === figma.mixed) {
      const seg = n.getStyledTextSegments(["fontSize", "fontName", "letterSpacing", "lineHeight", "fills"])[0];
      fs = seg.fontSize; fn = seg.fontName; ls = seg.letterSpacing; lh = seg.lineHeight; fills = seg.fills;
    }
    const lhPx = lh && lh.unit === "PIXELS" ? lh.value : lh && lh.unit === "PERCENT" ? r1(fs * lh.value / 100) : null;
    const lsPx = ls && ls.unit === "PIXELS" ? ls.value : ls && ls.unit === "PERCENT" ? r1(fs * ls.value / 100) : 0;
    const t = { t: n.characters.replace(/\s+/g, " ").trim().slice(0, 140), ...b, fs: fs, fw: weightOf(fn && fn.style),
      lh: lhPx, ls: lsPx, c: paint(fills), ta: n.textAlignHorizontal };
    if (n.opacity < 1) t.o = r1(n.opacity);
    if (n.textCase && n.textCase !== "ORIGINAL") t.tc = n.textCase;
    texts.push(t);
    return;
  }
  const b = rel(n);
  const fill = "fills" in n ? paint(n.fills) : null;
  const stroke = "strokes" in n ? paint(n.strokes) : null;
  const paints = !!(fill || stroke) || n.type === "VECTOR" || n.type === "LINE" || n.type === "BOOLEAN_OPERATION";
  const fx = "effects" in n ? n.effects.filter((e) => e.visible !== false && String(e.type).includes("SHADOW")) : [];
  if (b && (paints || fx.length) && n !== root) {
    const bx = { n: String(n.name).slice(0, 28), ty: n.type, id: n.id, ...b };
    if (fill) bx.f = fill;
    if (stroke) { bx.s = stroke; bx.sw = n.strokeWeight === figma.mixed ? null : n.strokeWeight; }
    if ("cornerRadius" in n && n.cornerRadius !== 0) {
      bx.r = n.cornerRadius === figma.mixed ? [n.topLeftRadius, n.topRightRadius, n.bottomRightRadius, n.bottomLeftRadius] : n.cornerRadius;
    }
    if ("layoutMode" in n && n.layoutMode !== "NONE") {
      bx.lm = n.layoutMode === "VERTICAL" ? "V" : "H";
      bx.gap = n.itemSpacing;
      bx.pad = [n.paddingTop, n.paddingRight, n.paddingBottom, n.paddingLeft];
    }
    if (n.opacity < 1) bx.o = r1(n.opacity);
    if (fx.length) bx.fx = fx.map((e) => ({ t: e.type === "DROP_SHADOW" ? "drop" : "inner", x: e.offset.x, y: e.offset.y, b: e.radius, c: hx(e.color) + "@" + r1(e.color.a) }));
    boxes.push(bx);
  } else if (b && "layoutMode" in n && n.layoutMode !== "NONE" && n !== root) {
    // an unpainted auto-layout frame still tells the audit the spacing system in use
    boxes.push({ n: String(n.name).slice(0, 28), ty: n.type, id: n.id, ...b, lm: n.layoutMode === "VERTICAL" ? "V" : "H",
      gap: n.itemSpacing, pad: [n.paddingTop, n.paddingRight, n.paddingBottom, n.paddingLeft], nofill: true });
  }
  if ("children" in n) for (const c of n.children) walk(c);
};
if ("children" in root) for (const c of root.children) walk(c);
const rootInfo = { fill: "fills" in root ? paint(root.fills) : null, lm: "layoutMode" in root ? root.layoutMode : null,
  gap: "itemSpacing" in root ? root.itemSpacing : null, pad: "paddingTop" in root ? [root.paddingTop, root.paddingRight, root.paddingBottom, root.paddingLeft] : null };
return { node: NODE_ID, name: root.name, w: r1(rb.width), h: r1(rb.height), root: rootInfo,
  counts: { texts: texts.length, boxes: boxes.length, capped: texts.length + boxes.length > MAX },
  texts, boxes };
