# UI Themes

Every page offers Light, Dark, and Cyber green in the header's Theme menu.
On first visit, the app follows the browser's light/dark preference. Selecting
a theme saves it locally under `ignatious-theme`, independent of sprint and
task settings. The choice persists across pages and reloads and synchronizes
between open tabs. With browser storage unavailable, selection still works
for the current page. Remove the saved key to follow system preferences again.

## Frontend Structure

- `static/themes.css` defines the palettes and theme-specific backgrounds.
- `static/ui.css` defines shared layout and components and imports the palettes.
- `static/planning.css` defines board, planning, task, and needed-work layouts.
- `static/theme.js` restores the theme before rendering and adds the shared menu.
- `static/cyber-green.css` is a compatibility import for older stylesheet URLs.

Load `theme.js` synchronously in the document head before `ui.css` to avoid a
flash of the wrong theme. Load `planning.css` after `ui.css` where needed.
Theme selection has no dependency on the API or page-specific JavaScript.

## Styling Components

Use semantic tokens instead of literal colors or color-specific names:

- Surfaces: `--bg`, `--surface`, `--surface-raised`.
- Text and borders: `--text`, `--muted`, `--line`, `--line-bright`.
- Interactive accents: `--accent`, `--accent-soft`, `--accent-hover`, `--on-accent`.
- Feedback: `--info`, `--success`, `--danger`, `--danger-soft`, `--on-danger`.
- Presentation: `--page-background`, `--header-background`, `--panel-background`,
  `--card-background`, `--shadow`, `--backdrop`.

Keep layout rules in component stylesheets and color decisions in `themes.css`.
Use CSS classes for presentation rather than inline styles in page logic.
To add a theme, define overrides on `:root[data-theme="name"]` and add its
value and menu label in `theme.js`. Set `color-scheme` so native form controls
and browser-provided UI use the matching appearance.

## Verification

Check all five pages at desktop and mobile widths with each theme. Confirm
reload/navigation persistence, system preference defaults, cross-tab changes,
invalid saved preferences, and operation when local storage is blocked. Check
focus rings, primary-button hover text, dialogs, error notices, and Team forms
alongside the board cards. Theme checks need not create or modify any task data.