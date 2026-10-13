# AI_COMMENT · Material 3-inspired refinement

**Reference:** [Google Material 3 Design Kit for Figma](https://www.figma.com/community/file/1035203688168086460/material-3-design-kit)

This product does not import the original Figma components or claim pixel-perfect parity. We use their spacing, shapes, selection states and elevation patterns, while retaining the **original blue AI_COMMENT palette**, cool-grayscale neutrals, application behavior, Korean Pretendard typography and verified logo.

## Token mapping

| Material 3 role | AI_COMMENT |
| --- | --- |
| Primary / on-primary | `--brand-600` / white |
| Primary container | `--md-primary-container` |
| On primary container | `--md-on-primary-container` |
| Surface | `--md-surface` |
| Surface container | `--md-surface-container` |
| Outline variant | `--md-outline-variant` |
| Medium/large corner | `--radius-lg`, `--md-shape-card` |
| Accessible focus state | `:focus-visible` outline |
| Reduced motion | `prefers-reduced-motion` |

The color hex values in `src/styles/tokens.css` are restored to the original pre-Material-3 blue/cool-gray palette. All `--md-*` color aliases in `src/styles/material3.css` reference those tokens, without introducing lavender hues. Elevation and shape remain Material-3-inspired. Colors and elevation live in `src/styles/tokens.css`; app-wide Material-inspired component treatments live in `src/styles/material3.css`, imported last in `main.tsx` so behavior-specific styles remain untouched. Avoid adding hardcoded new blue accents; use brand and surface roles.

## Screen-level design choices

- **Navigation:** tonal surface with pill-shaped active indicator; narrow layouts retain horizontally scrollable navigation and the account menu.
- **Recommendations:** one prominent filled CTA, grouped segmented input methods, focus outline and low-elevation cards.
- **Dashboard:** lightly tinted data-table headers, 18px cards, restrained KPI typography and normalized filters.
- **Persona and settings:** outlined selectable cards and a high-contrast selected state.
- **Accessibility:** button focus visibility, readable ink contrasts, minimum hit areas, reduced motion support.

## Validation

Run `npm ci && npm test && npm run lint && npm run build` from `frontend/`. UI review should cover desktop 1440px, tablet 900px, mobile 390px, scrolling navigation, account popover, and `/persona` selection. No backend API, route, or account state was modified.
