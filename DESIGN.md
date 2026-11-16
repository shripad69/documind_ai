# Design System: Grounded Document Intelligence Platform

## 1. Product Context & Subject
This platform is a high-precision, multi-tenant Retrieval-Augmented Generation (RAG) workspace for analysts, researchers, legal auditors, and technical operators.
Its primary job is verifying answers against primary source documents (PDF and DOCX) with deterministic, sentence-level citation references.
The visual identity must feel like a precision instrument: calm, authoritative, architectural, and distraction-free.

## 2. Token Architecture & Color System

The color system replaces pitch-black OLED surfaces (`#000000`) and purple/fuchsia neon glow gradients with a disciplined, cold-graphite slate palette.
All neutrals are tinted with a single consistent slate undertone (hue 220).
A single disciplined accent, Steel Cerulean (`#38BDF8` / `#0284C7`), provides visual hierarchy without chromatic competition.
Passage evidence uses a warm archival amber highlighter (`#F59E0B` at low opacity), providing immediate visual differentiation between interface controls and document evidence.

### CSS Variables Plan (`:root`)

```css
:root {
  /* Surfaces & Canvas (Cold Slate Graphite) */
  --bg-canvas: #0B0E14;
  --bg-surface-subtle: #111620;
  --bg-surface-raised: #171D28;
  --bg-surface-elevated: #1E2634;
  --bg-surface-active: #263142;
  --bg-surface-overlay: rgba(17, 22, 32, 0.88);

  /* Borders & Dividers */
  --border-subtle: rgba(255, 255, 255, 0.07);
  --border-default: rgba(255, 255, 255, 0.12);
  --border-strong: rgba(255, 255, 255, 0.20);
  --border-focus: #38BDF8;

  /* Typography Hierarchy */
  --text-primary: #F1F5F9;
  --text-secondary: #94A3B8;
  --text-tertiary: #64748B;
  --text-inverse: #0B0E14;

  /* Single Disciplined Accent: Steel Cerulean */
  --accent-primary: #0284C7;
  --accent-primary-hover: #0369A1;
  --accent-text: #38BDF8;
  --accent-subtle: rgba(56, 189, 248, 0.10);
  --accent-subtle-hover: rgba(56, 189, 248, 0.16);
  --accent-border: rgba(56, 189, 248, 0.32);

  /* Evidence & Grounding System */
  --evidence-mark-bg: rgba(245, 158, 11, 0.18);
  --evidence-mark-border: rgba(245, 158, 11, 0.45);
  --evidence-mark-text: #FDE68A;

  /* Functional Status */
  --status-ready: #10B981;
  --status-ready-bg: rgba(16, 185, 129, 0.12);
  --status-ready-border: rgba(16, 185, 129, 0.25);

  --status-warning: #F59E0B;
  --status-warning-bg: rgba(245, 158, 11, 0.12);
  --status-warning-border: rgba(245, 158, 11, 0.25);

  --status-danger: #EF4444;
  --status-danger-bg: rgba(239, 68, 68, 0.12);
  --status-danger-border: rgba(239, 68, 68, 0.25);

  /* Spatial & Concentric Radii */
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  /* Shadows (Neutral Hue-Tinted, Crisp) */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.35);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.45);
  --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.65);

  /* Motion & Interaction */
  --motion-duration-fast: 150ms;
  --motion-duration-base: 200ms;
  --motion-ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

## 3. Typography Scale & Hierarchy

Consolidate 5 fragmented font families (`Plus Jakarta Sans`, `Space Grotesk`, `JetBrains Mono`, `DM Sans`, `Manrope`) into a unified 2-family system:
1. Primary & Display Font: **Geist** (or system sans fallback `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`).
2. Data & Monospace Font: **Geist Mono** (for tabular data, citations, code blocks, document indices, timestamps).

### Type Hierarchy Specifications

| Level | Size | Weight | Line Height | Tracking | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Display Large | 28px | 600 (SemiBold) | 1.20 | -0.035em | Auth story headline, welcome screen primary heading |
| Title / Modal H2 | 18px | 600 (SemiBold) | 1.25 | -0.025em | Modal headers, panel titles, chat header title |
| Section Header / H3 | 14px | 600 (SemiBold) | 1.35 | -0.015em | Subsections, markdown headers, resource group labels |
| Body Regular | 13.5px | 400 (Regular) | 1.65 | 0 | Chat message text, source passage inspection, notes |
| Body Medium | 13px | 500 (Medium) | 1.50 | 0 | Buttons, input fields, navigation links |
| Caption / UI Small | 11.5px | 500 (Medium) | 1.40 | +0.01em | Metadata, secondary labels, file sizes, timestamps |
| Monospace Label | 11px | 600 (SemiBold) | 1.30 | +0.08em | Eyebrows, uppercase section titles, badge counts |
| Citation Reference | 11.5px | 600 (SemiBold) | 1.20 | 0 | Citation pills `[01]`, tabular indexing tags |

### Global Typography Rules
- Enforce `text-wrap: balance;` on all headings (`h1`, `h2`, `h3`).
- Enforce `text-wrap: pretty;` on all multi-line body paragraphs.
- Constrain reading text width in `.markdown-body` to `65ch` max width.
- Enforce `font-variant-numeric: tabular-nums;` on all metrics, counts, timestamps, and page numbers.
- Convert all uppercase labels to clean sentence case or restrained monospace tracked caps.

## 4. Spatial Scale & Concentric Radius Formula
- Max container widths:
  - Chat stream: `840px` centered.
  - Auth layout: `960px` centered.
  - Resource drawer: `440px`.
  - Modals: `440px` (Workspace dialog) / `480px` (Confirm dialog) / `640px` (Source inspection modal).
- Concentric radius hierarchy:
  - Outer modal card: `16px` radius with `20px` padding.
  - Inner inputs and interactive buttons: `8px` radius (`r_inner = r_outer - padding = 16px - 8px = 8px`).
  - Small badges and citation pills: `4px` - `6px` radius.

## 5. Signature Element: The Architectural Source & Evidence Ledger
Every generic RAG chatbot displays citations as rounded purple pills that pop open a basic modal.
Our product's signature element is an **Architectural Source & Evidence Ledger**:
- Citation pills are styled as precision index tags `[ref 01]` set in Geist Mono with tabular figures.
- Hovering or focusing a citation pill highlights the corresponding source card with a high-visibility left indicator hairline and subtle surface elevation.
- Clicking a citation opens a full-context **Passage Split-Inspector** with verified document metadata, exact sentence boundary highlighting in archival amber, and direct action to reveal the source file in the document library.
- The rest of the interface remains quiet, dark, and matte so the evidence ledger takes center stage.

## 6. Self-Critique & Calibration Checks

### Rejection of Cliché #1 (Purple-to-indigo gradients with Inter/Roboto):
- Completely purged all violet (`#8B5CF6`, `#A855F7`, `#C084FC`, `#7C3AED`, `#D946EF`), purple drop shadows, and Inter.
- Replaced with deep slate graphite and disciplined Steel Cerulean (`#38BDF8`).

### Rejection of Cliché #2 (Warm cream background with serif display and terracotta):
- No editorial serifs, no terracotta accents, no `#F4F1EA` paper textures.
- The aesthetic is an authentic engineering workstation, not an editorial lifestyle magazine.

### Rejection of Cliché #3 (Pitch-black with acid-green/vermilion neon):
- Pitch-black OLED (`#000000`) is replaced with tinted slate `#0B0E14` and `#111620`.
- No radioactive acid greens or neon reds.
- The accent saturation is capped at 75% for calm prolonged viewing.

### Rejection of Cliché #4 (Broadsheet hairline rules with zero border-radius):
- Balanced, intentional radii (`6px` to `16px`) ensure tactile affordance.
- Visual rhythm uses surface elevation steps rather than dense newspaper hairline borders.
