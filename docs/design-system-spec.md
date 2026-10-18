# SNEHA design system specification

Status: specification for implementation (Stage 8 visual refresh). Applies to
`apps/web_dashboard` (React, plain CSS) and `apps/patient_app` (Flutter, Material 3).
Owner brief: warm, dignified, calm, trustworthy, modern healthcare. Not a hospital
admin system, not a children's game, not a generic AI dashboard.

This document is normative: where it gives an exact value, use that value. Where two
engineers would otherwise make different choices, the choice is made here.

---

## 1. Brand principles

1. **Calm before clever.** One accent colour per screen. Do not use gradients,
   glows, confetti, bouncing or "sparkle" decoration. Motion only explains change.
2. **Dignity.** Adult language and adult visuals. No cartoon styling, no red
   crosses for wrong answers, no scores shown to the patient as grades.
3. **Warm, not clinical.** Cream page, white cards, forest/sage greens, one muted
   terracotta accent. Avoid pure-grey "admin" chrome and saturated blue "AI" chrome.
4. **Readable first.** Large type, strong contrast, generous spacing, short lines
   (max 70ch on web). Every text/background pair below is measured.
5. **Never colour alone.** Status always has text, plus a shape or icon. Charts
   always have value labels.
6. **Private by construction.** No web fonts, no CDNs, no network assets. Everything
   ships with the app or comes from the operating system.

---

## 2. Colour

### 2.1 Brand palette and what each colour is allowed to do

Measured against white `#FFFFFF`, cream `#FAF8F3` and pale sage `#E8EFE7`:

| Brand colour | Hex | vs white | vs cream | vs pale sage | Allowed use |
|---|---|---|---|---|---|
| Forest green | `#244C3A` | 9.68 | 9.12 | 8.26 | Hover/pressed primary, headings accent, high-emphasis text |
| Primary green | `#3F7057` | 5.73 | 5.40 | 4.89 | Primary buttons, links, selected states, chart series |
| Sage | `#A7BBA5` | 2.04 | 1.92 | 1.74 | **Decorative only** (illustration, dividers in hero areas). Never text, never a border that carries meaning |
| Pale sage | `#E8EFE7` | – | – | – | Selected/active backgrounds, chart track, gentle banners |
| Warm cream | `#FAF8F3` | – | – | – | Page background (web), scaffold (patient) |
| White | `#FFFFFF` | – | – | – | Cards, inputs, dialogs |
| Primary text | `#202C25` | – | – | – | All body text |
| Secondary text | `#626C65` | 5.45 | 5.14 | 4.65 | Web secondary text (passes AA everywhere, slim on pale sage). Patient app uses darker `#4F5A53` |
| Subtle border | `#E3E7E0` | 1.25 | 1.18 | 1.07 | **Decorative separators only** (card outline on cream, table row rules). Inputs/controls use `--color-border-strong` |
| Muted terracotta | `#C98168` | 3.08 | 2.90 | 2.63 | **Fails as text.** Decorative accent only (small marks, illustration, eyebrow rule). Meaningful use goes through `#B0634A` (non-text, >= 3:1) or `#9A5540` (text, >= 4.5:1) |

Adjustments made for contrast (owner asked to adjust only for this):

- Terracotta split into three tokens: `--color-accent` `#C98168` (decorative),
  `--color-accent-strong` `#B0634A` (chart accent, icons; 4.18 on cream, 4.44 on white),
  `--color-accent-text` `#9A5540` (text).
- Subtle border kept for decoration; added `--color-border-strong` `#7D8A80`
  (>= 3:1 on every light surface) for inputs, outlined buttons and table header rules.
- Patient app secondary text uses `#4F5A53` instead of `#626C65` (older eyes, small
  phones outdoors).

### 2.2 Web semantic tokens (light, dark, high contrast)

All tokens live in `apps/web_dashboard/src/styles/tokens.css`. Names keep the
existing `--color-*` prefix so the ~800 lines of `global.css` keep working; new
names are additions. Values:

| Token | Light | Dark | High contrast (light) |
|---|---|---|---|
| `--color-bg` | `#FAF8F3` | `#131A16` | `#FFFFFF` |
| `--color-surface` | `#FFFFFF` | `#1B241F` | `#FFFFFF` |
| `--color-surface-muted` | `#F1F4EF` | `#222D27` | `#EEF1EC` |
| `--color-surface-selected` (new) | `#E8EFE7` | `#2A3A31` | `#DCE8DD` |
| `--color-border` (decorative) | `#E3E7E0` | `#34423A` | `#4F5A53` |
| `--color-border-strong` (new; controls) | `#7D8A80` | `#7A887E` | `#2E3631` |
| `--color-text` | `#202C25` | `#EEF2EC` | `#000000` |
| `--color-text-muted` | `#626C65` | `#AEB8B0` | `#2E3631` |
| `--color-primary` | `#3F7057` | `#8FC4A5` | `#1B3A2C` |
| `--color-primary-strong` (new; hover/pressed) | `#244C3A` | `#B5DCC4` | `#000000` |
| `--color-primary-contrast` (text on primary) | `#FFFFFF` | `#10201A` | `#FFFFFF` |
| `--color-accent` (new; decorative) | `#C98168` | `#E0A48E` | `#6E3220` |
| `--color-accent-strong` (new; meaningful non-text) | `#B0634A` | `#E0A48E` | `#6E3220` |
| `--color-accent-text` (new) | `#9A5540` | `#E8B4A1` | `#6E3220` |
| `--color-focus` | `#1B5E8C` | `#8EC5F0` | `#0B3F66` |
| `--color-success-bg` / `-text` | `#E4F1E7` / `#1E5A35` | `#183020` / `#A7D9B5` | inherit light |
| `--color-warning-bg` / `-text` | `#FBF0DC` / `#7A4A00` | `#3A2C0E` / `#F2CD7E` | inherit light |
| `--color-danger-bg` / `-text` | `#FBE7E3` / `#9A2B1E` | `#3D1A16` / `#F5ADA0` | inherit light |
| `--color-danger-contrast` (new; text on danger button) | `#FFFFFF` | `#1B0A07` | `#FFFFFF` |
| `--color-info-bg` / `-text` | `#E5EEF5` / `#1C4A6E` | `#142838` / `#A8CBEA` | inherit light |
| `--color-neutral-bg` / `-text` | `#EEF1EC` / `#3F4842` | `#26302A` / `#D5DCD6` | inherit light |
| `--color-chart` (series) | `#3F7057` | `#8FC4A5` | `#1B3A2C` |
| `--color-chart-track` | `#E8EFE7` | `#2A3630` | `#DCE8DD` |
| `--color-chart-accent` (new; "usual"/comparison) | `#B0634A` | `#E0A48E` | `#6E3220` |
| `--color-chart-grid` (new) | `#E3E7E0` | `#34423A` | `#4F5A53` |

Why a blue focus ring in a green brand: the focus ring must be distinguishable
from the selected state (green) and from the primary button (green). A calm
blue, used only for focus, is the one non-brand hue allowed.

Info is a desaturated blue, not green, so "information" never reads as "success".

### 2.3 Flutter colour roles (patient app)

`SnehaTheme` stops using `ColorScheme.fromSeed` and builds the scheme explicitly
(`ColorScheme(...)` with every role below) so no generated tone can drift. Set
`surfaceTint: Colors.transparent` so Material 3 elevation does not tint cards
pink/green.

| ColorScheme role | Light | High contrast (light) | Dark | Dark high contrast |
|---|---|---|---|---|
| `surface` (scaffold) | `#FAF8F3` | `#FFFFFF` | `#131A16` | `#000000` |
| `surfaceContainerLowest` | `#FFFFFF` | `#FFFFFF` | `#0F1512` | `#000000` |
| `surfaceContainerLow` | `#F4F6F1` | `#FFFFFF` | `#171F1A` | `#000000` |
| `surfaceContainer` | `#EEF2EC` | `#F2F5F0` | `#1B241F` | `#000000` |
| `surfaceContainerHigh` (cards) | `#FFFFFF` | `#FFFFFF` | `#1B241F` | `#000000` |
| `surfaceContainerHighest` (photo fallback) | `#E2EAE0` | `#F2F5F0` | `#24302A` | `#1A1A1A` |
| `onSurface` | `#202C25` | `#000000` | `#EEF2EC` | `#FFFFFF` |
| `onSurfaceVariant` | `#4F5A53` | `#1F2622` | `#B7C1B9` | `#FFFFFF` |
| `primary` | `#3F7057` | `#1B3A2C` | `#8FC4A5` | `#CDEBD8` |
| `onPrimary` | `#FFFFFF` | `#FFFFFF` | `#10201A` | `#000000` |
| `primaryContainer` (positive banner, hero card) | `#D5E6D9` | `#D3E3D6` | `#24432F` | `#000000` |
| `onPrimaryContainer` | `#173326` | `#000000` | `#CDE8D6` | `#FFFFFF` |
| `secondary` | `#244C3A` | `#000000` | `#B5DCC4` | `#FFFFFF` |
| `onSecondary` | `#FFFFFF` | `#FFFFFF` | `#10201A` | `#000000` |
| `secondaryContainer` (gentle/neutral banner) | `#E8EFE7` | `#E8EFE7` | `#2A3A31` | `#000000` |
| `onSecondaryContainer` | `#1E2B22` | `#000000` | `#DCE6DA` | `#FFFFFF` |
| `tertiary` (terracotta: rest, caregiver) | `#9A5540` | `#6E3220` | `#E0A48E` | `#FFD2C2` |
| `onTertiary` | `#FFFFFF` | `#FFFFFF` | `#2A120A` | `#000000` |
| `tertiaryContainer` (rest banner) | `#F6E3DB` | `#F6E3DB` | `#4A2A1F` | `#000000` |
| `onTertiaryContainer` | `#5A2A1A` | `#000000` | `#F6DCD1` | `#FFFFFF` |
| `error` (forms/sync only, never in activities) | `#A0342A` | `#7F1D14` | `#F5ADA0` | `#FFB4A9` |
| `onError` | `#FFFFFF` | `#FFFFFF` | `#2A0A06` | `#000000` |
| `errorContainer` | `#FBE7E3` | `#FBE7E3` | `#3D1A16` | `#000000` |
| `onErrorContainer` | `#5C1A12` | `#000000` | `#F5ADA0` | `#FFFFFF` |
| `outline` (controls, card edge) | `#6E7A71` | `#000000` | `#7A887E` | `#FFFFFF` |
| `outlineVariant` (dividers) | `#E3E7E0` | `#4F5A53` | `#34423A` | `#BFBFBF` |
| `inverseSurface` / `onInverseSurface` | `#2B3530` / `#F0F3EE` | `#000000` / `#FFFFFF` | `#EEF2EC` / `#202C25` | `#FFFFFF` / `#000000` |
| `inversePrimary` | `#A7D3B8` | `#A7D3B8` | `#3F7057` | `#1B3A2C` |
| `shadow` / `scrim` | `#000000` | `#000000` | `#000000` | `#000000` |
| `surfaceTint` | transparent | transparent | transparent | transparent |

High contrast also sets border width 3 (already `borderWidth` in `theme.dart`).
Dark high contrast is pure black/white as today; keep that behaviour.

### 2.4 Measured contrast ratios

Produced by `contrast.py` (WCAG 2.x relative luminance, stdlib Python, run with
`python3 -I`). Thresholds: 4.5 for text, 3 for large text / UI borders / chart
marks, 7 for high-contrast themes. Rows marked `brand-raw` check the owner's
palette as given; their failures are why the adjusted tokens above exist and
those colours are restricted to decorative use. Every non-raw row passes.

| Theme | Pair | FG | BG | Ratio | Need | Result |
|---|---|---|---|---|---|---|
| brand-raw | raw brand check | `#626C65` | `#FFFFFF` | 5.45 | 4.5 | pass |
| brand-raw | raw brand check | `#626C65` | `#FAF8F3` | 5.14 | 4.5 | pass |
| brand-raw | raw brand check | `#626C65` | `#E8EFE7` | 4.65 | 4.5 | pass |
| brand-raw | raw brand check | `#C98168` | `#FFFFFF` | 3.08 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#C98168` | `#FAF8F3` | 2.90 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#C98168` | `#E8EFE7` | 2.63 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#3F7057` | `#FFFFFF` | 5.73 | 4.5 | pass |
| brand-raw | raw brand check | `#3F7057` | `#FAF8F3` | 5.40 | 4.5 | pass |
| brand-raw | raw brand check | `#3F7057` | `#E8EFE7` | 4.89 | 4.5 | pass |
| brand-raw | raw brand check | `#244C3A` | `#FFFFFF` | 9.68 | 4.5 | pass |
| brand-raw | raw brand check | `#244C3A` | `#FAF8F3` | 9.12 | 4.5 | pass |
| brand-raw | raw brand check | `#244C3A` | `#E8EFE7` | 8.26 | 4.5 | pass |
| brand-raw | raw brand check | `#A7BBA5` | `#FFFFFF` | 2.04 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#A7BBA5` | `#FAF8F3` | 1.92 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#A7BBA5` | `#E8EFE7` | 1.74 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#E3E7E0` | `#FFFFFF` | 1.25 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#E3E7E0` | `#FAF8F3` | 1.18 | 4.5 | FAIL (raw) |
| brand-raw | raw brand check | `#E3E7E0` | `#E8EFE7` | 1.07 | 4.5 | FAIL (raw) |
| web-light | text on bg | `#202C25` | `#FAF8F3` | 13.66 | 4.5 | pass |
| web-light | text-muted on bg | `#626C65` | `#FAF8F3` | 5.14 | 4.5 | pass |
| web-light | primary (link) on bg | `#3F7057` | `#FAF8F3` | 5.40 | 4.5 | pass |
| web-light | accent-text on bg | `#9A5540` | `#FAF8F3` | 5.28 | 4.5 | pass |
| web-light | border-strong (inputs) on bg | `#7D8A80` | `#FAF8F3` | 3.40 | 3 | pass |
| web-light | focus ring on bg | `#1B5E8C` | `#FAF8F3` | 6.54 | 3 | pass |
| web-light | text on surface | `#202C25` | `#FFFFFF` | 14.50 | 4.5 | pass |
| web-light | text-muted on surface | `#626C65` | `#FFFFFF` | 5.45 | 4.5 | pass |
| web-light | primary (link) on surface | `#3F7057` | `#FFFFFF` | 5.73 | 4.5 | pass |
| web-light | accent-text on surface | `#9A5540` | `#FFFFFF` | 5.60 | 4.5 | pass |
| web-light | border-strong (inputs) on surface | `#7D8A80` | `#FFFFFF` | 3.61 | 3 | pass |
| web-light | focus ring on surface | `#1B5E8C` | `#FFFFFF` | 6.94 | 3 | pass |
| web-light | text on muted | `#202C25` | `#F1F4EF` | 13.07 | 4.5 | pass |
| web-light | text-muted on muted | `#626C65` | `#F1F4EF` | 4.91 | 4.5 | pass |
| web-light | primary (link) on muted | `#3F7057` | `#F1F4EF` | 5.16 | 4.5 | pass |
| web-light | accent-text on muted | `#9A5540` | `#F1F4EF` | 5.05 | 4.5 | pass |
| web-light | border-strong (inputs) on muted | `#7D8A80` | `#F1F4EF` | 3.25 | 3 | pass |
| web-light | focus ring on muted | `#1B5E8C` | `#F1F4EF` | 6.25 | 3 | pass |
| web-light | text on sel | `#202C25` | `#E8EFE7` | 12.38 | 4.5 | pass |
| web-light | text-muted on sel | `#626C65` | `#E8EFE7` | 4.65 | 4.5 | pass |
| web-light | primary (link) on sel | `#3F7057` | `#E8EFE7` | 4.89 | 4.5 | pass |
| web-light | accent-text on sel | `#9A5540` | `#E8EFE7` | 4.79 | 4.5 | pass |
| web-light | border-strong (inputs) on sel | `#7D8A80` | `#E8EFE7` | 3.08 | 3 | pass |
| web-light | focus ring on sel | `#1B5E8C` | `#E8EFE7` | 5.93 | 3 | pass |
| web-light | on-primary on primary (button) | `#FFFFFF` | `#3F7057` | 5.73 | 4.5 | pass |
| web-light | on-primary on primary-strong (hover) | `#FFFFFF` | `#244C3A` | 9.68 | 4.5 | pass |
| web-light | primary button edge vs surface | `#3F7057` | `#FFFFFF` | 5.73 | 3 | pass |
| web-light | accent-strong (meaningful non-text) vs bg | `#B0634A` | `#FAF8F3` | 4.18 | 3 | pass |
| web-light | accent (decorative only, no meaning) vs bg | `#C98168` | `#FAF8F3` | 2.90 | 1.0 | pass |
| web-light | success text on its bg | `#1E5A35` | `#E4F1E7` | 7.02 | 4.5 | pass |
| web-light | success text on surface | `#1E5A35` | `#FFFFFF` | 8.17 | 4.5 | pass |
| web-light | danger text on its bg | `#9A2B1E` | `#FBE7E3` | 6.44 | 4.5 | pass |
| web-light | danger text on surface | `#9A2B1E` | `#FFFFFF` | 7.67 | 4.5 | pass |
| web-light | warning text on its bg | `#7A4A00` | `#FBF0DC` | 6.63 | 4.5 | pass |
| web-light | warning text on surface | `#7A4A00` | `#FFFFFF` | 7.48 | 4.5 | pass |
| web-light | info text on its bg | `#1C4A6E` | `#E5EEF5` | 7.93 | 4.5 | pass |
| web-light | info text on surface | `#1C4A6E` | `#FFFFFF` | 9.32 | 4.5 | pass |
| web-light | neutral text on its bg | `#3F4842` | `#EEF1EC` | 8.31 | 4.5 | pass |
| web-light | neutral text on surface | `#3F4842` | `#FFFFFF` | 9.47 | 4.5 | pass |
| web-light | on-danger on danger (danger button) | `#FFFFFF` | `#9A2B1E` | 7.67 | 4.5 | pass |
| web-light | chart series vs surface | `#3F7057` | `#FFFFFF` | 5.73 | 3 | pass |
| web-light | chart series vs track | `#3F7057` | `#E8EFE7` | 4.89 | 3 | pass |
| web-light | chart accent vs surface | `#B0634A` | `#FFFFFF` | 4.44 | 3 | pass |
| web-light | chart accent vs series (info only; must also differ by pattern/label) | `#B0634A` | `#3F7057` | 1.29 | 1.0 | pass |
| web-light | chart label (muted) on track | `#626C65` | `#E8EFE7` | 4.65 | 4.5 | pass |
| web-dark | text on bg | `#EEF2EC` | `#131A16` | 15.63 | 4.5 | pass |
| web-dark | text-muted on bg | `#AEB8B0` | `#131A16` | 8.66 | 4.5 | pass |
| web-dark | primary (link) on bg | `#8FC4A5` | `#131A16` | 8.94 | 4.5 | pass |
| web-dark | accent-text on bg | `#E8B4A1` | `#131A16` | 9.67 | 4.5 | pass |
| web-dark | border-strong (inputs) on bg | `#7A887E` | `#131A16` | 4.76 | 3 | pass |
| web-dark | focus ring on bg | `#8EC5F0` | `#131A16` | 9.60 | 3 | pass |
| web-dark | text on surface | `#EEF2EC` | `#1B241F` | 14.06 | 4.5 | pass |
| web-dark | text-muted on surface | `#AEB8B0` | `#1B241F` | 7.80 | 4.5 | pass |
| web-dark | primary (link) on surface | `#8FC4A5` | `#1B241F` | 8.04 | 4.5 | pass |
| web-dark | accent-text on surface | `#E8B4A1` | `#1B241F` | 8.70 | 4.5 | pass |
| web-dark | border-strong (inputs) on surface | `#7A887E` | `#1B241F` | 4.28 | 3 | pass |
| web-dark | focus ring on surface | `#8EC5F0` | `#1B241F` | 8.64 | 3 | pass |
| web-dark | text on muted | `#EEF2EC` | `#222D27` | 12.59 | 4.5 | pass |
| web-dark | text-muted on muted | `#AEB8B0` | `#222D27` | 6.98 | 4.5 | pass |
| web-dark | primary (link) on muted | `#8FC4A5` | `#222D27` | 7.20 | 4.5 | pass |
| web-dark | accent-text on muted | `#E8B4A1` | `#222D27` | 7.79 | 4.5 | pass |
| web-dark | border-strong (inputs) on muted | `#7A887E` | `#222D27` | 3.84 | 3 | pass |
| web-dark | focus ring on muted | `#8EC5F0` | `#222D27` | 7.74 | 3 | pass |
| web-dark | text on sel | `#EEF2EC` | `#2A3A31` | 10.61 | 4.5 | pass |
| web-dark | text-muted on sel | `#AEB8B0` | `#2A3A31` | 5.88 | 4.5 | pass |
| web-dark | primary (link) on sel | `#8FC4A5` | `#2A3A31` | 6.07 | 4.5 | pass |
| web-dark | accent-text on sel | `#E8B4A1` | `#2A3A31` | 6.56 | 4.5 | pass |
| web-dark | border-strong (inputs) on sel | `#7A887E` | `#2A3A31` | 3.23 | 3 | pass |
| web-dark | focus ring on sel | `#8EC5F0` | `#2A3A31` | 6.52 | 3 | pass |
| web-dark | on-primary on primary (button) | `#10201A` | `#8FC4A5` | 8.53 | 4.5 | pass |
| web-dark | on-primary on primary-strong (hover) | `#10201A` | `#B5DCC4` | 11.26 | 4.5 | pass |
| web-dark | primary button edge vs surface | `#8FC4A5` | `#1B241F` | 8.04 | 3 | pass |
| web-dark | accent-strong (meaningful non-text) vs bg | `#E0A48E` | `#131A16` | 8.32 | 3 | pass |
| web-dark | accent (decorative only, no meaning) vs bg | `#E0A48E` | `#131A16` | 8.32 | 1.0 | pass |
| web-dark | success text on its bg | `#A7D9B5` | `#183020` | 8.93 | 4.5 | pass |
| web-dark | success text on surface | `#A7D9B5` | `#1B241F` | 10.04 | 4.5 | pass |
| web-dark | danger text on its bg | `#F5ADA0` | `#3D1A16` | 8.37 | 4.5 | pass |
| web-dark | danger text on surface | `#F5ADA0` | `#1B241F` | 8.62 | 4.5 | pass |
| web-dark | warning text on its bg | `#F2CD7E` | `#3A2C0E` | 8.93 | 4.5 | pass |
| web-dark | warning text on surface | `#F2CD7E` | `#1B241F` | 10.47 | 4.5 | pass |
| web-dark | info text on its bg | `#A8CBEA` | `#142838` | 8.92 | 4.5 | pass |
| web-dark | info text on surface | `#A8CBEA` | `#1B241F` | 9.40 | 4.5 | pass |
| web-dark | neutral text on its bg | `#D5DCD6` | `#26302A` | 9.77 | 4.5 | pass |
| web-dark | neutral text on surface | `#D5DCD6` | `#1B241F` | 11.40 | 4.5 | pass |
| web-dark | on-danger on danger (danger button) | `#1B0A07` | `#F5ADA0` | 10.40 | 4.5 | pass |
| web-dark | chart series vs surface | `#8FC4A5` | `#1B241F` | 8.04 | 3 | pass |
| web-dark | chart series vs track | `#8FC4A5` | `#2A3630` | 6.36 | 3 | pass |
| web-dark | chart accent vs surface | `#E0A48E` | `#1B241F` | 7.48 | 3 | pass |
| web-dark | chart accent vs series (info only; must also differ by pattern/label) | `#E0A48E` | `#8FC4A5` | 1.07 | 1.0 | pass |
| web-dark | chart label (muted) on track | `#AEB8B0` | `#2A3630` | 6.16 | 4.5 | pass |
| web-high-contrast | text on bg | `#000000` | `#FFFFFF` | 21.00 | 7 | pass |
| web-high-contrast | text-muted on bg | `#2E3631` | `#FFFFFF` | 12.44 | 7 | pass |
| web-high-contrast | primary on bg | `#1B3A2C` | `#FFFFFF` | 12.44 | 7 | pass |
| web-high-contrast | border on bg | `#4F5A53` | `#FFFFFF` | 7.19 | 3 | pass |
| web-high-contrast | focus on bg | `#0B3F66` | `#FFFFFF` | 10.95 | 3 | pass |
| web-high-contrast | text on surface | `#000000` | `#FFFFFF` | 21.00 | 7 | pass |
| web-high-contrast | text-muted on surface | `#2E3631` | `#FFFFFF` | 12.44 | 7 | pass |
| web-high-contrast | primary on surface | `#1B3A2C` | `#FFFFFF` | 12.44 | 7 | pass |
| web-high-contrast | border on surface | `#4F5A53` | `#FFFFFF` | 7.19 | 3 | pass |
| web-high-contrast | focus on surface | `#0B3F66` | `#FFFFFF` | 10.95 | 3 | pass |
| web-high-contrast | text on muted | `#000000` | `#EEF1EC` | 18.43 | 7 | pass |
| web-high-contrast | text-muted on muted | `#2E3631` | `#EEF1EC` | 10.92 | 7 | pass |
| web-high-contrast | primary on muted | `#1B3A2C` | `#EEF1EC` | 10.92 | 7 | pass |
| web-high-contrast | border on muted | `#4F5A53` | `#EEF1EC` | 6.31 | 3 | pass |
| web-high-contrast | focus on muted | `#0B3F66` | `#EEF1EC` | 9.61 | 3 | pass |
| web-high-contrast | text on sel | `#000000` | `#DCE8DD` | 16.63 | 7 | pass |
| web-high-contrast | text-muted on sel | `#2E3631` | `#DCE8DD` | 9.85 | 7 | pass |
| web-high-contrast | primary on sel | `#1B3A2C` | `#DCE8DD` | 9.85 | 7 | pass |
| web-high-contrast | border on sel | `#4F5A53` | `#DCE8DD` | 5.70 | 3 | pass |
| web-high-contrast | focus on sel | `#0B3F66` | `#DCE8DD` | 8.67 | 3 | pass |
| web-high-contrast | on-primary on primary | `#FFFFFF` | `#1B3A2C` | 12.44 | 7 | pass |
| flutter-light | onSurface on surface | `#202C25` | `#FAF8F3` | 13.66 | 4.5 | pass |
| flutter-light | onSurfaceVariant on surface | `#4F5A53` | `#FAF8F3` | 6.78 | 4.5 | pass |
| flutter-light | primary (icons/outlined label) on surface | `#3F7057` | `#FAF8F3` | 5.40 | 4.5 | pass |
| flutter-light | outline (button/input border) on surface | `#6E7A71` | `#FAF8F3` | 4.22 | 3 | pass |
| flutter-light | onSurface on lowest | `#202C25` | `#FFFFFF` | 14.50 | 4.5 | pass |
| flutter-light | onSurfaceVariant on lowest | `#4F5A53` | `#FFFFFF` | 7.19 | 4.5 | pass |
| flutter-light | primary (icons/outlined label) on lowest | `#3F7057` | `#FFFFFF` | 5.73 | 4.5 | pass |
| flutter-light | outline (button/input border) on lowest | `#6E7A71` | `#FFFFFF` | 4.48 | 3 | pass |
| flutter-light | onSurface on low | `#202C25` | `#F4F6F1` | 13.32 | 4.5 | pass |
| flutter-light | onSurfaceVariant on low | `#4F5A53` | `#F4F6F1` | 6.61 | 4.5 | pass |
| flutter-light | primary (icons/outlined label) on low | `#3F7057` | `#F4F6F1` | 5.26 | 4.5 | pass |
| flutter-light | outline (button/input border) on low | `#6E7A71` | `#F4F6F1` | 4.12 | 3 | pass |
| flutter-light | onSurface on cont | `#202C25` | `#EEF2EC` | 12.81 | 4.5 | pass |
| flutter-light | onSurfaceVariant on cont | `#4F5A53` | `#EEF2EC` | 6.35 | 4.5 | pass |
| flutter-light | primary (icons/outlined label) on cont | `#3F7057` | `#EEF2EC` | 5.06 | 4.5 | pass |
| flutter-light | outline (button/input border) on cont | `#6E7A71` | `#EEF2EC` | 3.96 | 3 | pass |
| flutter-light | onSurface on high | `#202C25` | `#E8EFE7` | 12.38 | 4.5 | pass |
| flutter-light | onSurfaceVariant on high | `#4F5A53` | `#E8EFE7` | 6.14 | 4.5 | pass |
| flutter-light | primary (icons/outlined label) on high | `#3F7057` | `#E8EFE7` | 4.89 | 4.5 | pass |
| flutter-light | outline (button/input border) on high | `#6E7A71` | `#E8EFE7` | 3.83 | 3 | pass |
| flutter-light | onSurface on highest | `#202C25` | `#E2EAE0` | 11.79 | 4.5 | pass |
| flutter-light | onSurfaceVariant on highest | `#4F5A53` | `#E2EAE0` | 5.85 | 4.5 | pass |
| flutter-light | primary (icons/outlined label) on highest | `#3F7057` | `#E2EAE0` | 4.66 | 4.5 | pass |
| flutter-light | outline (button/input border) on highest | `#6E7A71` | `#E2EAE0` | 3.65 | 3 | pass |
| flutter-light | onPrimary on primary (BigButton) | `#FFFFFF` | `#3F7057` | 5.73 | 4.5 | pass |
| flutter-light | onPrimaryContainer on primaryContainer (positive banner) | `#173326` | `#D5E6D9` | 10.50 | 4.5 | pass |
| flutter-light | onSecondaryContainer on secondaryContainer (gentle banner) | `#1E2B22` | `#E8EFE7` | 12.59 | 4.5 | pass |
| flutter-light | onTertiaryContainer on tertiaryContainer (rest banner) | `#5A2A1A` | `#F6E3DB` | 9.51 | 4.5 | pass |
| flutter-light | onTertiary on tertiary | `#FFFFFF` | `#9A5540` | 5.60 | 4.5 | pass |
| flutter-light | onError on error | `#FFFFFF` | `#A0342A` | 6.96 | 4.5 | pass |
| flutter-light | onErrorContainer on errorContainer | `#5C1A12` | `#FBE7E3` | 10.95 | 4.5 | pass |
| flutter-light | tertiary icon on surface | `#9A5540` | `#FAF8F3` | 5.28 | 3 | pass |
| flutter-hc | onSurface on surface | `#000000` | `#FFFFFF` | 21.00 | 7 | pass |
| flutter-hc | onSurfaceVariant on surface | `#1F2622` | `#FFFFFF` | 15.46 | 7 | pass |
| flutter-hc | primary on surface | `#1B3A2C` | `#FFFFFF` | 12.44 | 7 | pass |
| flutter-hc | outlineVariant on surface | `#4F5A53` | `#FFFFFF` | 7.19 | 3 | pass |
| flutter-hc | error on surface | `#7F1D14` | `#FFFFFF` | 10.06 | 7 | pass |
| flutter-hc | onSurface on cont | `#000000` | `#F2F5F0` | 19.09 | 7 | pass |
| flutter-hc | onSurfaceVariant on cont | `#1F2622` | `#F2F5F0` | 14.05 | 7 | pass |
| flutter-hc | primary on cont | `#1B3A2C` | `#F2F5F0` | 11.31 | 7 | pass |
| flutter-hc | outlineVariant on cont | `#4F5A53` | `#F2F5F0` | 6.54 | 3 | pass |
| flutter-hc | error on cont | `#7F1D14` | `#F2F5F0` | 9.14 | 7 | pass |
| flutter-hc | onPrimary on primary | `#FFFFFF` | `#1B3A2C` | 12.44 | 7 | pass |
| flutter-hc | onpc on pc | `#000000` | `#D3E3D6` | 15.73 | 7 | pass |
| flutter-hc | onsc on sc | `#000000` | `#E8EFE7` | 17.93 | 7 | pass |
| flutter-hc | ontc on tc | `#000000` | `#F6E3DB` | 16.93 | 7 | pass |
| flutter-dark | onSurface on surface | `#EEF2EC` | `#131A16` | 15.63 | 4.5 | pass |
| flutter-dark | onSurfaceVariant on surface | `#B7C1B9` | `#131A16` | 9.55 | 4.5 | pass |
| flutter-dark | primary on surface | `#8FC4A5` | `#131A16` | 8.94 | 4.5 | pass |
| flutter-dark | outline on surface | `#7A887E` | `#131A16` | 4.76 | 3 | pass |
| flutter-dark | onSurface on cont | `#EEF2EC` | `#1B241F` | 14.06 | 4.5 | pass |
| flutter-dark | onSurfaceVariant on cont | `#B7C1B9` | `#1B241F` | 8.60 | 4.5 | pass |
| flutter-dark | primary on cont | `#8FC4A5` | `#1B241F` | 8.04 | 4.5 | pass |
| flutter-dark | outline on cont | `#7A887E` | `#1B241F` | 4.28 | 3 | pass |
| flutter-dark | onSurface on high | `#EEF2EC` | `#24302A` | 12.11 | 4.5 | pass |
| flutter-dark | onSurfaceVariant on high | `#B7C1B9` | `#24302A` | 7.41 | 4.5 | pass |
| flutter-dark | primary on high | `#8FC4A5` | `#24302A` | 6.93 | 4.5 | pass |
| flutter-dark | outline on high | `#7A887E` | `#24302A` | 3.69 | 3 | pass |
| flutter-dark | onPrimary on primary | `#10201A` | `#8FC4A5` | 8.53 | 4.5 | pass |
| flutter-dark | onpc on pc | `#CDE8D6` | `#24432F` | 8.40 | 4.5 | pass |
| flutter-dark | onsc on sc | `#DCE6DA` | `#2A3A31` | 9.37 | 4.5 | pass |
| flutter-dark | ontc on tc | `#F6DCD1` | `#4A2A1F` | 9.79 | 4.5 | pass |
| flutter-light | onSecondary on secondary | `#FFFFFF` | `#244C3A` | 9.68 | 4.5 | pass |
| flutter-light | secondary on surface | `#244C3A` | `#FAF8F3` | 9.12 | 4.5 | pass |
| flutter-light | tertiary (text) on surface | `#9A5540` | `#FAF8F3` | 5.28 | 4.5 | pass |
| flutter-light | error text on surface | `#A0342A` | `#FAF8F3` | 6.55 | 4.5 | pass |
| flutter-light | onInverseSurface on inverseSurface (snackbar) | `#F0F3EE` | `#2B3530` | 11.34 | 4.5 | pass |
| flutter-light | inversePrimary (snackbar action) on inverseSurface | `#A7D3B8` | `#2B3530` | 7.65 | 4.5 | pass |
| flutter-hc | tertiary on surface | `#6E3220` | `#FFFFFF` | 9.81 | 7 | pass |
| flutter-hc | onTertiary on tertiary | `#FFFFFF` | `#6E3220` | 9.81 | 7 | pass |
| flutter-hc | onSecondary on secondary | `#FFFFFF` | `#000000` | 21.00 | 7 | pass |
| flutter-dark | onTertiary on tertiary | `#2A120A` | `#E0A48E` | 8.30 | 4.5 | pass |
| flutter-dark | tertiary on surface | `#E0A48E` | `#131A16` | 8.32 | 4.5 | pass |
| flutter-dark | error on surface | `#F5ADA0` | `#131A16` | 9.58 | 4.5 | pass |
| flutter-dark | onErrorContainer on errorContainer | `#F5ADA0` | `#3D1A16` | 8.37 | 4.5 | pass |
| flutter-dark | onSecondary on secondary | `#10201A` | `#B5DCC4` | 11.26 | 4.5 | pass |
| flutter-dark | onInverseSurface on inverseSurface | `#202C25` | `#EEF2EC` | 12.81 | 4.5 | pass |
| flutter-dark | inversePrimary on inverseSurface | `#3F7057` | `#EEF2EC` | 5.06 | 4.5 | pass |
| flutter-dark-hc | onSurface on surface | `#FFFFFF` | `#000000` | 21.00 | 7 | pass |
| flutter-dark-hc | onPrimary on primary | `#000000` | `#CDEBD8` | 16.47 | 7 | pass |
| flutter-dark-hc | primary on surface | `#CDEBD8` | `#000000` | 16.47 | 7 | pass |
| flutter-dark-hc | tertiary on surface | `#FFD2C2` | `#000000` | 15.25 | 7 | pass |
| flutter-dark-hc | error on surface | `#FFB4A9` | `#000000` | 12.35 | 7 | pass |
| flutter-dark-hc | outlineVariant on surface | `#BFBFBF` | `#000000` | 11.42 | 3 | pass |
| flutter-dark-hc | onSurface on surfaceContainerHighest | `#FFFFFF` | `#1A1A1A` | 17.40 | 7 | pass |
| web-high-contrast | accent-text on #FFFFFF | `#6E3220` | `#FFFFFF` | 9.81 | 7 | pass |
| web-high-contrast | border-strong on #FFFFFF | `#2E3631` | `#FFFFFF` | 12.44 | 3 | pass |
| web-high-contrast | accent-text on #EEF1EC | `#6E3220` | `#EEF1EC` | 8.61 | 7 | pass |
| web-high-contrast | border-strong on #EEF1EC | `#2E3631` | `#EEF1EC` | 10.92 | 3 | pass |
| web-high-contrast | accent-text on #DCE8DD | `#6E3220` | `#DCE8DD` | 7.77 | 7 | pass |
| web-high-contrast | border-strong on #DCE8DD | `#2E3631` | `#DCE8DD` | 9.85 | 3 | pass |
| web-high-contrast | on-danger on danger button | `#FFFFFF` | `#9A2B1E` | 7.67 | 4.5 | pass |
| web-high-contrast | chart series vs track | `#1B3A2C` | `#DCE8DD` | 9.85 | 3 | pass |

Re-run after any colour change: `python3 -I contrast.py --md`. The script was
written in the session scratchpad, not the repo; if it should be kept, copy it to
`apps/web_dashboard/scripts/contrast.py` (stdlib only). In the `flutter-light` rows,
`high` means `#E8EFE7` (pale sage, the `secondaryContainer` value) and `lowest` means
white, which is also the card colour.

### 2.5 Colour usage rules

- Page = `bg` (cream). Content containers = `surface` (white). Never white-on-white
  without a `--color-border` outline or `--shadow-1`.
- Primary green is used for: the one primary button per view, links, selected
  nav/tab indicator, chart series, focus-adjacent selected states. Not for large
  background fills (except the patient's big primary button).
- Terracotta appears at most once per view as decoration (e.g. the 3px rule under
  the brand mark, the "usual pattern" marker in charts, the patient's rest/caregiver
  affordances). Never for errors.
- Danger red is for destructive actions (revoke consent, delete memory) and real
  errors only. Review flags are `warning` (amber), not danger: they are prompts to
  talk, not alarms.
- The patient app never shows red during an activity. Wrong answers use
  `secondaryContainer` (sage) and the words "Let's try another one".

---

## 3. Typography

### 3.1 Font decision

**Web:** system font stack only. Do **not** add `Inter` (it would render on some
clinicians' machines and not others, making screenshots, line breaks and table
widths inconsistent) and never add an `@font-face` or Google Fonts link.

```css
--font-sans: system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans',
  'Noto Sans Devanagari', 'Noto Sans Bengali', 'Nirmala UI',
  'Kohinoor Devanagari', 'Kohinoor Bangla', sans-serif;
--font-numeric: var(--font-sans); /* always with font-variant-numeric: tabular-nums */
```

`Nirmala UI` (Windows) and `Kohinoor` (macOS/iOS) cover Devanagari and
Bengali-Assamese when Noto is absent. Set `lang` on `<html>` (already done by
`SettingsProvider`) so the browser picks the right script fallback.

**Flutter:** explicit family on the theme, with Indic fallbacks. No new pub
packages, no `google_fonts`, no bundled font files.

```dart
const kFontFamily = 'Roboto';
const kFontFallback = <String>['Noto Sans Devanagari', 'Noto Sans Bengali', 'Noto Sans'];
ThemeData(fontFamily: kFontFamily, fontFamilyFallback: kFontFallback, ...)
```

Why this matters now: in the baseline app renders every **button label is drawn
as boxes**. `theme.dart` builds button text with a free-standing
`TextStyle(fontSize: 22, ...)` that has no `fontFamily`, so it does not inherit the
text theme's family and the test renderer substitutes its placeholder font.
Rule: **never construct a raw `TextStyle` inside the theme or widgets; always derive
from a `textTheme` slot with `copyWith`** (e.g. `text.labelLarge`), and set
`fontFamily`/`fontFamilyFallback` on `ThemeData` so every slot carries them. Screenshot
tooling must load Roboto from the Flutter SDK cache (`bin/cache/artifacts/material_fonts`)
via `FontLoader` in the test harness; this is test-only and adds no runtime dependency.

### 3.2 Web type scale

Root stays `font-size: 100%` (16px) so `data-text-size` (112.5% / 125%) keeps
scaling everything. Body is 17px as today.

| Role | Token | Size | Weight | Line height | Notes |
|---|---|---|---|---|---|
| Page title (`h1`, `.page-header h1`) | `--text-page-title` | 1.75rem (28px) | 650 (fallback 600) | 1.25 | `letter-spacing: -0.01em`; mobile 1.5rem |
| Section title (`h2`) | `--text-section-title` | 1.3125rem (21px) | 600 | 1.3 | |
| Card title (`.card__title`, `h3`) | `--text-card-title` | 1.125rem (18px) | 600 | 1.35 | |
| Body | `--font-size-md` | 1.0625rem (17px) | 400 | 1.6 | max 70ch for prose |
| Small / meta | `--font-size-sm` | 0.9375rem (15px) | 400 | 1.5 | never smaller than 15px for content |
| Eyebrow (`.eyebrow`) | `--text-eyebrow` | 0.8125rem (13px) | 600 | 1.4 | uppercase, `letter-spacing: 0.06em`, `--color-text-muted`. Only place below 15px |
| Label (`.field__label`, `th`) | `--text-label` | 0.9375rem | 600 | 1.4 | |
| Button | inherit `--font-size-md` | 1.0625rem | 600 | 1.2 | |
| Nav item | `--font-size-md` | 1.0625rem | 500, current 600 | 1.3 | |
| Chart label / axis | `--text-chart` | 0.875rem (14px) | 500 | 1.3 | tabular-nums; values above bars 600 |
| Metric value (`.metric__value`) | `--text-metric` | 1.75rem | 650 | 1.1 | `font-variant-numeric: tabular-nums` |
| Table numeric cells | body | 17px | 400 | 1.5 | `.num` class: right-aligned, tabular-nums |

Global rule: `table, .metric__value, .chart, .num, time { font-variant-numeric: tabular-nums; }`.

### 3.3 Flutter text theme (patient)

All slots `copyWith` from `base.textTheme`, colour `onSurface`. Sizes in logical
pixels (sp); system text scaling stays respected (do not clamp `textScaler` below
1.0; clamp at max 2.0 only in fixed-height control bars).

| Slot | Size | Weight | Height | Use |
|---|---|---|---|---|
| `displaySmall` | 40 | w600 | 1.15 | Rest screen headline only |
| `headlineLarge` | 34 | w700 | 1.2 | Greeting ("Namaste, Aita") |
| `headlineMedium` | 30 | w600 | 1.2 | Screen titles without AppBar |
| `headlineSmall` | 26 | w600 | 1.25 | Activity prompt ("What is this?"), MessageView title |
| `titleLarge` | 24 | w600 | 1.3 | Card titles, AppBar title |
| `titleMedium` | 22 | w600 | 1.3 | Option-button labels if not using labelLarge |
| `bodyLarge` | 22 | w400 | 1.5 | Default patient body (was 20; raise to 22 for primary reading surfaces) |
| `bodyMedium` | 20 | w400 | 1.5 | Secondary body. **Floor for patient text** |
| `bodySmall` | 18 | w400 | 1.45 | Caregiver-only metadata (e.g. "Chosen on this phone") |
| `labelLarge` | 22 | w600 | 1.2 | All buttons (Filled/Outlined/Text) |
| `labelMedium` | 20 | w600 | 1.2 | Chips, runner control bar labels |
| `labelSmall` | 18 | w500 | 1.2 | Never used for patient-facing text |

AppBar `titleTextStyle` = `titleLarge`. Runner round counter ("1 of 3") = `titleMedium`.
For Devanagari/Bengali, keep `height >= 1.4` on body slots (matras and conjuncts clip
below that).

---

## 4. Space, shape, elevation, motion

### 4.1 Spacing (4px base)

| Token (web) | Value | Flutter constant |
|---|---|---|
| `--space-1` | 4px | `Space.xs = 4` |
| `--space-2` | 8px | `Space.sm = 8` |
| `--space-3` | 12px | `Space.md = 12` |
| `--space-4` | 16px | `Space.lg = 16` |
| `--space-5` (new) | 20px | `Space.xl = 20` |
| `--space-6` | 24px | `Space.xxl = 24` |
| `--space-8` | 32px | `Space.xxxl = 32` |
| `--space-10` (new) | 40px | – |
| `--space-12` (new) | 48px | – |

Web: card padding `--space-6` desktop, `--space-4` below 640px; gap between cards
`--space-4`; between page sections `--space-8`. Patient: page padding 24 (20 on
widths < 380), gap between stacked buttons 12, card padding 20.

### 4.2 Radii and borders

| Token | Web | Flutter | Use |
|---|---|---|---|
| `--radius-sm` | 8px | 12 | inputs, buttons (web), badges use pill |
| `--radius-md` | 12px | 16 | cards (web), notices, patient buttons and inputs |
| `--radius-lg` (new) | 16px | 20 | dialogs, patient cards, hero card |
| `--radius-pill` (new) | 999px | StadiumBorder | badges, chips |

Borders: 1px `--color-border` for cards/separators; 1.5px (web renders 2px on 1x)
`--color-border-strong` for inputs; 2px for outlined buttons. Patient: card edge 1px
`outlineVariant` (normal), 3px `outline` (high contrast); outlined buttons 2px `outline`.

### 4.3 Elevation (restrained)

```css
--shadow-1: 0 1px 2px rgb(32 44 37 / 6%), 0 1px 3px rgb(32 44 37 / 4%);   /* cards */
--shadow-2: 0 4px 12px rgb(32 44 37 / 8%), 0 2px 4px rgb(32 44 37 / 5%);  /* menus, drawer */
--shadow-3: 0 12px 32px rgb(32 44 37 / 14%);                              /* dialogs */
```
Dark mode and high contrast: all shadows `none`; separation is by border. Flutter:
`elevation: 0` everywhere except dialogs/bottom sheets (`elevation: 2` with
transparent `surfaceTint`).

### 4.4 Motion

| Token | Value | Use |
|---|---|---|
| `--motion-fast` | 120ms | hover, colour, focus |
| `--motion-base` | 200ms | drawer, tabs indicator, notice appear |
| `--motion-slow` | 280ms | dialog, page transitions (Flutter) |
| `--ease` | `cubic-bezier(0.2, 0, 0, 1)` | all |

Keep `--transition` as alias of `var(--motion-fast) var(--ease)`.

Reduced motion (web: `prefers-reduced-motion: reduce` **or** `[data-motion='reduced']`;
Flutter: `reduceMotion` already merges system + setting in `app.dart`):
- All durations become `0ms` (web: set the three tokens to `0ms`; do not use
  `transition: none` on individual rules).
- No transforms/slides; colour changes may remain instant.
- Spinners: replace rotating indicator with static text "Loading..." (web) /
  `LinearProgressIndicator(value: null)` is still motion, so show the label only
  plus a static icon in Flutter.
- Flutter: keep `_NoTransitionsBuilder`; game feedback (flip, highlight) must check
  `RoundContext.reduceMotion` and use `Duration.zero`.

---

## 5. Component patterns

### 5.1 Dashboard (web)

**Buttons** (`Button.tsx`, `.button*`)
- Height `min-height: 44px` (`--control-min-height`); compact variant not allowed.
  Padding `0 var(--space-5)`; radius `--radius-sm`; weight 600; icon gap `--space-2`.
- Primary: bg `--color-primary`, text `--color-primary-contrast`, border same.
  Hover/active: `--color-primary-strong`.
- Secondary: bg `--color-surface`, text `--color-primary-strong`, 2px border
  `--color-border-strong`; hover bg `--color-surface-selected`.
- Ghost: transparent, text `--color-primary`, no border; hover bg `--color-surface-muted`;
  underline on hover so it still reads as interactive.
- Danger: bg `--color-danger-text`, text `--color-danger-contrast`. Always confirm
  through a Dialog.
- Disabled: keep opacity 0.6 **plus** `DisabledReason` text nearby (already a pattern).
- Pending: keep "Please wait..." text + `aria-busy`.
- One primary button per card/dialog. The header "Sign out" is ghost, not secondary.

**Inputs** (`Field.tsx`, `.input`, `.field*`)
- 44px min height, padding `var(--space-2) var(--space-3)`, bg `--color-surface`,
  2px `--color-border-strong`, radius `--radius-sm`. Hover border `--color-text-muted`.
  Focus: border `--color-primary` + global focus ring.
- Label above (600, `--text-label`), hint below label in muted, error below input
  in `--color-danger-text` prefixed with "Error:" text or an icon (not colour alone).
- `select`: same as input, custom chevron via inline SVG data URI in CSS
  (`currentColor` not available; use `--color-text-muted` hex per theme) or keep native.
- Textarea: min-height 6rem, `resize: vertical`.
- Date inputs: `color-scheme` follows theme so the native picker is legible in dark.

**Cards and sections** (`Card.tsx`, `.card`)
- bg `--color-surface`, 1px `--color-border`, radius `--radius-md`, `--shadow-1`,
  padding `--space-6`. `.card__header` flex with title left, actions right.
- A page section without a card uses an `h2` + `--space-8` top margin; do not
  nest cards inside cards. Inner groupings use `.surface-muted` panels
  (bg `--color-surface-muted`, radius `--radius-md`, no shadow) - this is what
  `.metric` becomes.

**Metrics** (`.metric`, `.summary-grid`): bg `--color-surface-muted`, label 15px
muted 500, value `--text-metric` tabular, helper line 15px muted. 4 columns at
>= 1024px, 2 at >= 560px, 1 below.

**Tabs** (`Tabs.tsx`, `.tabs__*`) and **sub-navigation** (`.subnav`)
- Replace the black inverted pill selected state. Tabs are a segmented control:
  container bg `--color-surface-muted`, radius `--radius-sm`, padding 4px; tab
  min-height 44px (container grows), selected tab bg `--color-surface`,
  `--shadow-1`, text `--color-text`, weight 600, plus a 2px inset bottom bar
  `--color-primary` (non-colour cue: weight + bar + `aria-selected`).
- `.subnav` (patient record sections): underline style, current item 3px bottom
  border `--color-primary`, weight 600. On < 768px it scrolls horizontally with
  `scroll-snap-type: x proximity` and a fade mask at the edge (the baseline cuts off
  "Consent & data" with no affordance).

**App shell, sidebar and drawer** (`AppShell.tsx`, `.app-*`)
- >= 1024px: left sidebar 248px fixed, bg `--color-surface`, right border
  `--color-border`. Top: brand "SNEHA" (20px, 700, `--color-primary-strong`) with a
  24px x 3px `--color-accent` rule beneath. Nav items 44px, radius `--radius-sm`,
  icon optional 20px; current item bg `--color-surface-selected`, text
  `--color-primary-strong`, weight 600, 3px left bar `--color-primary`
  (`aria-current="page"`, already set by NavLink). Bottom: user name + role,
  "Sign out" ghost button. Main area max-width `--content-max-width` (72rem),
  padding `--space-8` `--space-6`.
- < 1024px: top bar 56px (brand left, "Menu" button right with text label, not
  icon-only), opens a left drawer (`<dialog>` or `aria-modal` panel), width
  `min(320px, 85vw)`, `--shadow-2`, backdrop `rgb(0 0 0 / 40%)`, Escape and backdrop
  close, focus trapped and returned to the Menu button. Reduced motion: no slide.
- Skip link, `ConnectionBanner` and footer stay; banner sits above main content,
  full width of the main column.

**Page header** (`PageHeader.tsx`, `.page-header`): optional `.eyebrow`, `h1`
(`--text-page-title`), lede muted max 60ch, actions right-aligned on desktop and
stacked full-width below 640px. Bottom margin `--space-6`.

**Status badges** (`StatusBadge.tsx`, `.badge`): keep symbol + text. Pill radius,
padding `2px var(--space-3)`, 15px 600, bg/text from the tone pair, plus 1px border
in the text colour at 25% (`color-mix(in srgb, currentColor 25%, transparent)`) so
badges hold up on muted surfaces. Add `info` tone (symbol `◆`).

**Notices** (`.notice--*`): radius `--radius-md`, padding `--space-4`, 4px left
border in the tone's text colour, title 600. Always start with a title or an icon +
visually-hidden tone word ("Note:", "Warning:"). Info for explanations ("About these
numbers"), warning for data gaps, success for confirmations, danger for failures.

**Toasts**: none today; if added, bottom-right (bottom-center < 640px), max 24rem,
surface + `--shadow-2` + 4px left tone border, `role="status"`, auto-dismiss only for
success (6s, paused on hover/focus), never for errors. Reduced motion: no slide.

**Dialogs** (`Dialog.tsx`, `.dialog*`): width `min(40rem, 100%)`, radius
`--radius-lg`, padding `--space-6`, `--shadow-3`, backdrop `rgb(20 26 22 / 45%)`.
Title `--text-section-title`. Footer right-aligned: secondary (Cancel) then primary
or danger; stacked full-width with primary on top below 480px.

**Tables** (`Table.tsx`, `.table*`): header row 15px 600 muted, bottom border 2px
`--color-border-strong`; rows 1px `--color-border`, cell padding
`var(--space-3) var(--space-4)`, min row height 44px; numeric columns `.num`
(right, tabular). Zebra off. Row hover bg `--color-surface-muted` only if the row is
interactive. `.table-wrap` keeps horizontal scroll with `tabindex="0"` and a
caption; below 640px prefer the card-list alternative already used for sessions.

**Charts** (`.chart*`, `AnalyticsView.tsx`): single hue `--color-chart` on
`--color-chart-track`; comparison/"usual" uses `--color-chart-accent` as a 2px
dashed reference line or outlined bar, never a second filled hue alone. Every bar
has its value label above (600, `--text-chart`) and date label below (muted).
Missing days render as an empty track with an en dash label and a diagonal-hatch
pattern (`repeating-linear-gradient` with `--color-chart-grid`), so "no data" is not
read as "zero". Bar radius 4px top only. Chart title is an `h3` card title. The
Charts/Table toggle stays; the table is the accessible equivalent.

**Review flags** (`.review-flag*`): surface card, 4px left border
`--color-warning-text`, symbol ▲ + "May be worth reviewing" label. Not danger.

**States** (`States.tsx`, `.state*`)
- Empty: centred, `--space-8` padding, 1px dashed `--color-border-strong`, title 600,
  one-line explanation, optional primary action. Copy explains what will appear.
- Loading: skeleton blocks (bg `--color-surface-muted`, radius `--radius-sm`) for
  known layouts; otherwise "Loading..." text with `role="status"`. No spinner when
  reduced motion.
- Error: notice-danger styling (not dashed), title + plain-language cause + "Try
  again" secondary button.
- Offline: `ConnectionBanner` stays warning tone, full-width, text "You are offline.
  Showing saved information from <time>." with ▲ symbol.

### 5.2 Patient app (Flutter)

**Big action button** (`BigButton` in `lib/ui/widgets.dart`)
- Filled: bg `primary`, fg `onPrimary`, min height 64, full width, radius 16,
  padding h20/v14, label `labelLarge` (22/600), icon 28 leading, 12 gap. Pressed
  overlay `onPrimary` at 12%. Disabled: `onSurface` 12% bg, `onSurface` 50% text, and
  if the reason is not obvious, a `bodyMedium` explanation below.
- Secondary (outlined): bg `surfaceContainerLowest`, 2px `outline`, fg `onSurface`,
  icon `primary`.
- Vertical spacing between stacked BigButtons: 12 (the existing
  `Padding(vertical: 6)` on each button already gives this; keep it).
- Home activity list buttons (the three dark slabs in the baseline) become
  **secondary** BigButtons; only one filled button per screen (the hero "Start").

**Suggestion hero card** (`features/home/suggestion_card.dart`)
- `Card` with bg `primaryContainer`, no outline in normal mode (3px `outline` in high
  contrast), radius 20, padding 24.
- Order: small header row (icon `Icons.spa_outlined` 28 in `onPrimaryContainer`,
  "Suggested for you" `titleMedium`), activity title `headlineSmall`, reason
  `bodyLarge`, source line ("Chosen on this phone") `bodySmall` `onSurfaceVariant`,
  then filled BigButton "Start". Replace the sparkle icon (reads as "AI").
- Break suggestion variant uses `tertiaryContainer` + bedtime icon and a secondary
  button; it must look as positive as the activity suggestion.

**Status/info cards** ("Working on this phone", "Today"): `SnehaCard` on
`surfaceContainerHigh` (white), 1px `outlineVariant`, icon 28 `primary`, title
`titleLarge`, body `bodyLarge`. Not filled with a tint (baseline uses a pink tint
from the seed: removed by explicit scheme).

**Option buttons for games** (`_OptionButton` in `activities/rounds/choice_round.dart`,
tiles in `pairs_round.dart`, `sequence_round.dart`)
- Outlined BigButton, min height 72 (above the 64 floor because they are the main
  target), label `titleMedium` 22/600 centered, 2px `outline`, bg
  `surfaceContainerLowest`, gap 12.
- Chosen-correct: bg `primaryContainer`, 3px `primary` border, leading
  `Icons.check_circle` + label stays; announce via `NoticeBanner(positive)`.
- Chosen-not-right: bg `surfaceContainer`, label and icon at 60% (not 40%) opacity,
  dashed or 1px border, trailing text "Not this one" under label (`bodyMedium`),
  disabled. No red, no X icon, no shake.
- Image options: same frame (radius 16, 2px outline) around `MemoryPhoto`, label
  text under the image (not only `semanticLabel`) so the choice is readable.
- Pairs tiles: square, min 96x96, radius 16; face-down = `secondaryContainer` with a
  centred sage motif icon; matched = `primaryContainer` + check icon + 3px border.

**Runner control bar** (`activity_runner_screen.dart` `bottomNavigationBar`)
- Container bg `surfaceContainerLow`, top 1px `outlineVariant`, padding 12/16,
  SafeArea.
- Layout keeps 2+2+1 but hierarchy changes: Pause/Resume and Hint are outlined
  (`outline` 2px, `onSurface`); Skip is a text-style button with outline 1px
  `outlineVariant`; **Stop** is outlined with `onSurfaceVariant` text (calm, not
  red); **"I'm tired, rest now"** is full width, `tertiaryContainer` bg,
  `onTertiaryContainer` fg, bedtime icon, no border: inviting, never alarming.
- Each control min height 64, label `labelMedium` (20/600), icon 26, `maxLines: 2`.
  At text scale > 1.3 the bar becomes a single column, and the screen body scrolls
  above it; never ellipsize the Stop or Rest labels.
- AppBar "Caregiver" action: `TextButton.icon` fg `tertiary`, min 48x48.

**Gentle feedback banners** (`NoticeBanner`)
- Three tones by enum (replace `positive` bool with `tone`):
  `positive` = `primaryContainer`/`onPrimaryContainer`, icon check_circle;
  `gentle` (try again, hint, info) = `secondaryContainer`/`onSecondaryContainer`,
  icon lightbulb/info; `rest` = `tertiaryContainer`/`onTertiaryContainer`, icon spa.
- Radius 16, padding 16, border 1px `outlineVariant` (3px `outline` in HC), icon 28,
  text `bodyLarge`. `liveRegion: true` kept. No auto-dismiss.

**Rest / stop / paused** (paused overlay, `result_screen.dart`)
- Paused overlay: bg `surface`, centred MessageView with `pause_circle_outline`
  in `primary` 72, title "Taking a pause" `headlineSmall`, filled "Carry on" button.
- Stop confirmation dialog: title "Stop for now?", body reassures progress is
  saved; buttons "Keep going" (filled) and "Stop for now" (outlined). Never
  danger-coloured.
- Rest result: `displaySmall` headline ("Well done for today"), `bodyLarge`
  message, `tertiaryContainer` band with bedtime icon; one filled "Back to home".

**Loading / empty / error / offline**: `LoadingView` keeps label text; in reduced
motion show a static `Icons.hourglass_empty` 48 instead of the spinner.
`MessageView` icon 64 in `primary` (`onSurfaceVariant` for errors, never `error`).
Offline is not an error in the patient app: "Working on this phone" card style.

**Read-aloud button** (`lib/ui/read_aloud.dart`): outlined 64dp, `volume_up` icon
in `primary`; when disabled by setting, show it disabled with the explanation line
below in `bodyMedium onSurfaceVariant` (as now).

---

## 6. Existing code mapping (reuse first)

| Existing | File | Decision | Change |
|---|---|---|---|
| Token file | `apps/web_dashboard/src/styles/tokens.css` | Refine | Replace values per section 2.2/3/4; add new tokens; restructure themes per section 7.2 |
| `.app-header`, `.app-nav`, `.app-brand`, `.app-user` | `src/styles/global.css`, `src/components/layout/AppShell.tsx` | Replace | Sidebar (>=1024) + top bar/drawer (<1024); new `.app-sidebar`, `.app-topbar`, `.app-drawer`; keep `NAV` data and NavLink |
| `.skip-link`, `.app-footer`, `.visually-hidden` | `global.css` | Keep | Colours via tokens only |
| `.page-header`, `.eyebrow` | `global.css`, `components/ui/PageHeader.tsx` | Refine | Type tokens; actions slot layout |
| `.card`, `.card__header`, `.card__title` | `global.css`, `components/ui/Card.tsx` | Refine | radius 12, `--shadow-1`, title token |
| `.button`, `--secondary`, `--ghost`, `--danger`, `--block` | `global.css`, `components/ui/Button.tsx` | Refine | Colours/hover per 5.1; Sign out → ghost |
| `.field*`, `.input`, `.input--textarea`, `.checkbox` | `global.css`, `components/ui/Field.tsx` | Refine | `--color-border-strong`, focus border |
| `.badge--*` | `global.css`, `components/ui/StatusBadge.tsx` | Keep + extend | Add `info` tone, subtle border |
| `.notice--*` | `global.css` | Refine | Left border, titles |
| `.state--*` | `global.css`, `components/ui/States.tsx` | Refine | Error uses notice styling; skeleton loading |
| `.tabs__list`, `.tabs__tab` | `global.css`, `components/ui/Tabs.tsx` | Refine | Segmented control; drop inverted black selected |
| `.subnav` | `global.css` | Refine | Scroll affordance on mobile |
| `.dialog*` | `global.css`, `components/ui/Dialog.tsx` | Refine | radius 16, `--shadow-3`, mobile button stacking |
| `.table`, `.table-wrap` | `global.css`, `components/ui/Table.tsx` | Refine | header rule, `.num` |
| `.metric*`, `.summary-grid` | `global.css`, `components/analytics/AnalyticsView.tsx` | Refine | Muted panel, tabular, grid breakpoints |
| `.chart*`, `.chart-grid` | `global.css`, `AnalyticsView.tsx` | Refine | Green series, hatch for missing, accent reference |
| `.review-flag*` | `global.css`, `components/analytics/ReviewFlagsPanel.tsx` | Refine | Warning left border + symbol |
| `.connection-banner` | `global.css`, `components/ConnectionBanner.tsx` | Keep | Token colours |
| `.disabled-reason` | `global.css`, `components/ui/DisabledReason.tsx` | Keep | – |
| `.memory-card`, `.photo*`, `.timeline*`, `.person-row`, `.chip*`, `.definition-list*`, `.pairing-code`, `.landing*` | `global.css` | Keep | Inherit new tokens; no structural change |
| `SettingsProvider` data attributes | `src/state/SettingsProvider.tsx` | Keep (+ optional) | Optional `data-theme` (section 7.2) |
| `SnehaTheme` | `apps/patient_app/lib/ui/theme.dart` | Refine (substantial) | Explicit ColorScheme, font family, text from slots, component themes per 7.1 |
| `BigButton` | `lib/ui/widgets.dart` | Keep | Styling flows from theme; no API change |
| `SnehaCard` | `lib/ui/widgets.dart` | Keep | Icon size 28 |
| `NoticeBanner` | `lib/ui/widgets.dart` | Refine | `tone` enum (keep `positive` as deprecated alias) |
| `MessageView`, `LoadingView`, `PageBody` | `lib/ui/widgets.dart` | Keep | Reduced-motion static loading |
| `MemoryPhoto` | `lib/ui/widgets.dart` | Keep | – |
| `ReadAloudButton` | `lib/ui/read_aloud.dart` | Keep | – |
| `_OptionButton` | `lib/activities/rounds/choice_round.dart` | Refine | 72 min height, chosen states per 5.2 |
| Pair / sequence tiles | `lib/activities/rounds/pairs_round.dart`, `sequence_round.dart` | Refine | Tile colours/sizes per 5.2 |
| `_ControlButton` + control bar | `lib/features/activities/activity_runner_screen.dart` | Refine | Hierarchy per 5.2; Rest in tertiaryContainer |
| Suggestion card | `lib/features/home/suggestion_card.dart` | Refine | Hero layout, no sparkle icon |
| Home activity buttons | `lib/features/home/home_screen.dart` | Refine | Secondary BigButtons |
| Result screen | `lib/features/activities/result_screen.dart` | Refine | Rest styling |

---

## 7. Exact implementation references

### 7.1 Flutter `ThemeData`

```dart
// lib/ui/theme.dart (shape of the result; values from section 2.3/3.3)
static const kFontFamily = 'Roboto';
static const kFontFallback = ['Noto Sans Devanagari', 'Noto Sans Bengali', 'Noto Sans'];

static ThemeData _build(Brightness b, bool hc, bool reduceMotion) {
  final scheme = _scheme(b, hc);            // explicit ColorScheme(...) per table 2.3
  final base = ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: kFontFamily,
    fontFamilyFallback: kFontFallback,
  );
  final t = base.textTheme.apply(bodyColor: scheme.onSurface, displayColor: scheme.onSurface);
  final text = t.copyWith(/* sizes per 3.3, every slot via t.<slot>!.copyWith */);
  final border = hc ? 3.0 : 1.0;
  final label = text.labelLarge!;           // NEVER a raw TextStyle
  return base.copyWith(
    scaffoldBackgroundColor: scheme.surface,
    textTheme: text,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface, foregroundColor: scheme.onSurface,
      elevation: 0, scrolledUnderElevation: 0, surfaceTintColor: Colors.transparent,
      titleTextStyle: text.titleLarge, toolbarHeight: 64),
    filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(
      minimumSize: const Size(double.infinity, minTouchTarget),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      textStyle: label, backgroundColor: scheme.primary, foregroundColor: scheme.onPrimary,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)))),
    outlinedButtonTheme: OutlinedButtonThemeData(style: OutlinedButton.styleFrom(
      minimumSize: const Size(double.infinity, minTouchTarget),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      textStyle: label, foregroundColor: scheme.onSurface,
      backgroundColor: scheme.surfaceContainerLowest,
      side: BorderSide(color: scheme.outline, width: hc ? 3 : 2),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)))),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(
      minimumSize: const Size(48, 48), textStyle: text.labelMedium,
      foregroundColor: scheme.primary)),
    iconTheme: IconThemeData(color: scheme.onSurface, size: 28),
    cardTheme: CardThemeData(
      elevation: 0, color: scheme.surfaceContainerHigh, surfaceTintColor: Colors.transparent,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: hc ? scheme.outline : scheme.outlineVariant, width: border))),
    inputDecorationTheme: InputDecorationTheme(
      filled: true, fillColor: scheme.surfaceContainerLowest,
      contentPadding: const EdgeInsets.all(20),
      labelStyle: text.bodyMedium, hintStyle: text.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
      errorMaxLines: 3,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: scheme.outline, width: border)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: scheme.outline, width: border)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: scheme.primary, width: 3))),
    dialogTheme: DialogThemeData(backgroundColor: scheme.surfaceContainerHigh,
      surfaceTintColor: Colors.transparent, elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      titleTextStyle: text.headlineSmall, contentTextStyle: text.bodyLarge),
    bottomSheetTheme: BottomSheetThemeData(backgroundColor: scheme.surfaceContainerHigh,
      surfaceTintColor: Colors.transparent,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20)))),
    snackBarTheme: SnackBarThemeData(backgroundColor: scheme.inverseSurface,
      contentTextStyle: text.bodyMedium?.copyWith(color: scheme.onInverseSurface),
      actionTextColor: scheme.inversePrimary, behavior: SnackBarBehavior.floating),
    switchTheme: const SwitchThemeData(materialTapTargetSize: MaterialTapTargetSize.padded),
    dividerTheme: DividerThemeData(color: scheme.outlineVariant, thickness: 1),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: scheme.primary,
      linearTrackColor: scheme.secondaryContainer),
    materialTapTargetSize: MaterialTapTargetSize.padded,
    visualDensity: VisualDensity.standard,
    pageTransitionsTheme: reduceMotion ? /* existing _NoTransitionsBuilder map */ : null,
  );
}
```

Constants stay: `SnehaTheme.minTouchTarget = 64`, `kTileMinSize`. Add
`SnehaTheme.optionMinHeight = 72`. Nothing interactive below 48x48 (AppBar
actions included).

### 7.2 CSS custom properties (complete list)

`tokens.css` structure (order matters):

```css
:root {                                   /* light (default) */
  color-scheme: light;
  /* type */
  --font-sans: system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans',
    'Noto Sans Devanagari', 'Noto Sans Bengali', 'Nirmala UI',
    'Kohinoor Devanagari', 'Kohinoor Bangla', sans-serif;
  --font-size-sm: 0.9375rem;  --font-size-md: 1.0625rem;
  --font-size-lg: 1.25rem;    --font-size-xl: 1.625rem;  --font-size-2xl: 2rem;
  --text-page-title: 1.75rem; --text-section-title: 1.3125rem;
  --text-card-title: 1.125rem; --text-label: 0.9375rem; --text-eyebrow: 0.8125rem;
  --text-chart: 0.875rem;     --text-metric: 1.75rem;
  --line-height: 1.6;         --line-height-tight: 1.25;
  /* space */
  --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem; --space-4: 1rem;
  --space-5: 1.25rem; --space-6: 1.5rem; --space-8: 2rem; --space-10: 2.5rem; --space-12: 3rem;
  /* shape */
  --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-pill: 999px;
  --control-min-height: 44px; --content-max-width: 72rem; --sidebar-width: 248px;
  /* colour */
  --color-bg: #FAF8F3; --color-surface: #FFFFFF; --color-surface-muted: #F1F4EF;
  --color-surface-selected: #E8EFE7;
  --color-border: #E3E7E0; --color-border-strong: #7D8A80;
  --color-text: #202C25; --color-text-muted: #626C65;
  --color-primary: #3F7057; --color-primary-strong: #244C3A; --color-primary-contrast: #FFFFFF;
  --color-accent: #C98168; --color-accent-strong: #B0634A; --color-accent-text: #9A5540;
  --color-focus: #1B5E8C;
  --color-success-bg: #E4F1E7; --color-success-text: #1E5A35;
  --color-warning-bg: #FBF0DC; --color-warning-text: #7A4A00;
  --color-danger-bg: #FBE7E3;  --color-danger-text: #9A2B1E; --color-danger-contrast: #FFFFFF;
  --color-info-bg: #E5EEF5;    --color-info-text: #1C4A6E;
  --color-neutral-bg: #EEF1EC; --color-neutral-text: #3F4842;
  --color-chart: #3F7057; --color-chart-track: #E8EFE7;
  --color-chart-accent: #B0634A; --color-chart-grid: #E3E7E0;
  /* elevation */
  --shadow-1: 0 1px 2px rgb(32 44 37 / 6%), 0 1px 3px rgb(32 44 37 / 4%);
  --shadow-2: 0 4px 12px rgb(32 44 37 / 8%), 0 2px 4px rgb(32 44 37 / 5%);
  --shadow-3: 0 12px 32px rgb(32 44 37 / 14%);
  --shadow-card: var(--shadow-1);          /* alias kept for existing rules */
  /* motion */
  --motion-fast: 120ms; --motion-base: 200ms; --motion-slow: 280ms;
  --ease: cubic-bezier(0.2, 0, 0, 1);
  --transition: var(--motion-fast) var(--ease);
}

/* Dark: system preference unless the viewer forced light. */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) { /* dark block */ }
}
:root[data-theme='dark'] { /* same dark block */ }
```

Dark block (identical in both places; keep them adjacent and in sync):
```css
  color-scheme: dark;
  --color-bg: #131A16; --color-surface: #1B241F; --color-surface-muted: #222D27;
  --color-surface-selected: #2A3A31;
  --color-border: #34423A; --color-border-strong: #7A887E;
  --color-text: #EEF2EC; --color-text-muted: #AEB8B0;
  --color-primary: #8FC4A5; --color-primary-strong: #B5DCC4; --color-primary-contrast: #10201A;
  --color-accent: #E0A48E; --color-accent-strong: #E0A48E; --color-accent-text: #E8B4A1;
  --color-focus: #8EC5F0;
  --color-success-bg: #183020; --color-success-text: #A7D9B5;
  --color-warning-bg: #3A2C0E; --color-warning-text: #F2CD7E;
  --color-danger-bg: #3D1A16;  --color-danger-text: #F5ADA0; --color-danger-contrast: #1B0A07;
  --color-info-bg: #142838;    --color-info-text: #A8CBEA;
  --color-neutral-bg: #26302A; --color-neutral-text: #D5DCD6;
  --color-chart: #8FC4A5; --color-chart-track: #2A3630;
  --color-chart-accent: #E0A48E; --color-chart-grid: #34423A;
  --shadow-1: none; --shadow-2: 0 0 0 1px var(--color-border); --shadow-3: 0 0 0 1px var(--color-border);
```

High contrast, reduced motion, text size (after the dark rules so they win):
```css
:root[data-contrast='high'] {
  color-scheme: light;
  --color-bg: #FFFFFF; --color-surface: #FFFFFF; --color-surface-muted: #EEF1EC;
  --color-surface-selected: #DCE8DD;
  --color-border: #4F5A53; --color-border-strong: #2E3631;
  --color-text: #000000; --color-text-muted: #2E3631;
  --color-primary: #1B3A2C; --color-primary-strong: #000000; --color-primary-contrast: #FFFFFF;
  --color-accent: #6E3220; --color-accent-strong: #6E3220; --color-accent-text: #6E3220;
  --color-focus: #0B3F66;
  /* status pairs: the light values (re-declare all ten so dark values cannot leak) */
  --color-success-bg: #E4F1E7; --color-success-text: #1E5A35;
  --color-warning-bg: #FBF0DC; --color-warning-text: #7A4A00;
  --color-danger-bg: #FBE7E3;  --color-danger-text: #9A2B1E; --color-danger-contrast: #FFFFFF;
  --color-info-bg: #E5EEF5;    --color-info-text: #1C4A6E;
  --color-neutral-bg: #EEF1EC; --color-neutral-text: #3F4842;
  --color-chart: #1B3A2C; --color-chart-track: #DCE8DD;
  --color-chart-accent: #6E3220; --color-chart-grid: #4F5A53;
  --shadow-1: none; --shadow-2: 0 0 0 2px #000; --shadow-3: 0 0 0 2px #000;
}
@media (prefers-reduced-motion: reduce) {
  :root { --motion-fast: 0ms; --motion-base: 0ms; --motion-slow: 0ms; }
}
:root[data-motion='reduced'] { --motion-fast: 0ms; --motion-base: 0ms; --motion-slow: 0ms; }
:root[data-text-size='large'] { font-size: 112.5%; }
:root[data-text-size='larger'] { font-size: 125%; }
```

Notes for implementers:
- **There is no `data-theme` mechanism today.** `SettingsProvider.tsx` sets only
  `data-text-size`, `data-contrast` and `data-motion`; dark mode follows
  `prefers-color-scheme` alone. The `data-theme` selectors above are inert until a
  Settings option (System / Light / Dark, default System) sets
  `document.documentElement.dataset.theme`; adding that option is optional. Do not
  set `data-theme` to `'system'`; remove the attribute instead.
- **Existing bug fixed by this structure:** the current
  `:root[data-contrast='high']` overrides `--color-bg`/`--color-text` but not
  `--color-surface`, so a dark-mode viewer who turns on high contrast gets black text
  on the dark `#1f1d18` surface. High contrast is now a complete light palette that
  re-declares every colour token. (A dark high-contrast variant can be added later
  as `:root[data-contrast='high'][data-theme='dark']`.)
- `color-scheme` per theme replaces the current `color-scheme: light dark` so native
  controls (date pickers in Activity trends) match.
- Focus ring stays global: `:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }`.
  On primary buttons add `box-shadow: 0 0 0 2px var(--color-surface)` inside the ring.
- Do not hard-code any hex in `global.css` after the refresh; `grep -E '#[0-9a-fA-F]{3,6}' src/styles/global.css`
  should return nothing.

### 7.3 Acceptance checks

1. `python3 -I contrast.py` reports `fails 0` for any changed token.
2. Dashboard at 390px: no horizontal page scroll; drawer opens/closes with keyboard;
   every control >= 44px.
3. Patient app at 360x640 with text scale 1.3: runner bar labels not truncated,
   all primary controls >= 64dp, nothing below 48dp; button labels render glyphs
   (not boxes) in screenshot tests.
4. Hindi, Assamese and Bengali strings render without tofu on Android (Roboto +
   Noto fallbacks) and on web (system stack).
5. Every status (badge, notice, flag, chart gap, game feedback) is understandable in
   greyscale.

## Premium visual theme for the dashboard (2026-10-18)

`apps/web_dashboard/src/styles/refresh.css` (loaded after `global.css`) gives the caregiver
dashboard a bright, animated look without changing layout or behaviour:

- Brand gradient deep emerald → teal → indigo/violet, slowly shifting on the person banner,
  sign-in panel, selected menu item, primary buttons and logo mark. White text only sits
  on colours dark enough for at least 4.5:1.
- Glass sidebar and top bar over two softly drifting colour blobs.
- Gradient page titles with a pink-amber accent bar; gradient section markers.
- Colour-coded number tiles (emerald, blue, rose, violet, amber) with a glowing corner orb,
  uppercase labels, larger numbers and a coloured glow on hover.
- Chart bars in emerald and violet gradients that grow in; cards, tiles and memory cards
  rise in with a short stagger; a light sweep across the banner and buttons.

Every colour has light, dark and extra-high-contrast values (high contrast: solid colours,
black borders, no glow, glass or decorations). **All animation stops** with the system
"reduce motion" setting or SNEHA's own setting. This theme is for caregivers only; the
patient app keeps its calm design (no motion that competes for attention).

### Patient app (same palette, calmer motion)

`lib/ui/theme.dart` uses the same emerald (#047857), teal (#0F766E) and violet (#6D28D9)
roles (dark: #6EE7B7, #5EEAD4, #C4B5FD) with bright containers. `SnehaThemeFlags` carries
the brand, soft and rest gradients (none in extra high contrast) and the reduce-motion
flag. The main next step (`BigButton`) is a gradient with a soft glow; the suggestion card
is a pastel gradient (violet-rose when it suggests a rest); the home choices have
colour-coded icons; "SNEHA" is gradient text. The only motion is `EntranceFade`: page
content fades and lifts in **once** when a page opens, and not at all with reduced motion.
Unlike the dashboard there is no looping, drifting or sweeping motion: the app is used by
people with dementia, and activities keep their still, focused layout.
