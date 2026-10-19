# Tailwind migration

This update moves dashboard, tutorial and chart styling into Tailwind utilities in the React components. It uses Tailwind CSS 4 with the official PostCSS integration.

## Install the patch

This patch expects the tutorial and interactive-chart updates to have been applied. The hover patch may be present or absent; this migration does not patch the old CSS files.

Stop the frontend server. Save signal-tailwind-migration.patch in the market-lab project root, then run in Windows Command Prompt:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-tailwind-migration.patch
git apply signal-tailwind-migration.patch
cd frontend
npm install -D tailwindcss@4 @tailwindcss/postcss@4 postcss@latest
npm install tailwind-merge
npx tsc --noEmit
npm run build
npm run dev
```

The npm commands update your existing package.json and lockfile without replacing your locally upgraded Next.js version. Open http://localhost:3000. Python startup is unchanged.

Do not run `npx tailwindcss init -p`: this project uses Tailwind 4's CSS-first configuration and @tailwindcss/postcss.

## Where to edit

| File | Change here |
| --- | --- |
| app/page.tsx | Page layout, sidebar, asset cards, metrics, forms and tables |
| app/ui.tsx | Shared Button, Panel, Pill and label/select utilities |
| app/tailwind.css | Tailwind import and shared theme colors/font |
| app/research-tutorial.tsx | Tutorial content, layout and controls |
| app/interactive-chart.tsx | Graph controls, tooltip and SVG interactions |
| postcss.config.mjs | Tailwind's PostCSS integration |

app/layout.tsx now loads app/tailwind.css. The former globals.css and interactive-chart.css are no longer imported; editing them has no effect. Once you have verified the migration and retained any custom edits elsewhere, these obsolete files can be removed. They are left in place so patch application does not depend on whether the previous hover patch was installed.

## Common small edits

In a component's className:

- Padding: change p-4 to p-5.
- Gap: change gap-3 to gap-4.
- Rounded corners: change rounded-md to rounded-xl.
- Typography: change text-xs to text-sm.
- Border: change border-line to border-accent.
- Hover: edit hover:bg-[#293844] in the shared Button definition.
- Responsive columns: edit grid-cols-4 or max-[1150px]:grid-cols-2.

Use complete literal utility strings. For conditional styling:

```tsx
className={selected ? 'border-accent bg-accent/10' : 'border-line bg-surface'}
```

Avoid dynamically building fragments such as `bg-${color}`; Tailwind detects complete class names at build time.

Shared theme colors are defined once in app/tailwind.css:

```css
@theme {
  --color-accent: #b9f275;
}
```

Changing this token updates utilities such as text-accent, bg-accent and border-accent. Some original exact colors remain as arbitrary Tailwind values for visual continuity.

Button and Panel use tailwind-merge so local className overrides can replace conflicting default utilities. Example:

```tsx
<Button variant="primary" className="rounded-xl px-6">Run experiment</Button>
```

## Tutorial and chart behavior

Tutorial targets use data-tour attributes independently of styling. Preserve these attributes if you rearrange JSX. Active targets are styled through a Tailwind data-attribute variant on the page wrapper.

Interactive chart functionality is retained: hover tooltips, zoom buttons, drag to pan, Reset, All and keyboard controls. Tooltip position and SVG coordinates remain calculated at runtime. These are data-driven coordinates, not a separate CSS styling system.

## Checks and limits

- TypeScript check passed.
- Tailwind/PostCSS compiled successfully, including responsive variants, motion preferences and tutorial highlight styles.
- Patch application and the resulting file contents were checked against the previous tutorial + interactive-chart sources.
- The production Next.js build was attempted but blocked before compilation by the authoring environment's uv_resident_set_memory error. Browser visual QA was unavailable.
- The local authoring workspace has Next.js 15; the user's upgraded Next.js 16 installation still requires the local build check above.

After installation, check all four tabs, run a forecast, inspect/zoom/pan the chart, and replay the tutorial at desktop and mobile widths. Backend API behavior and stored data are unchanged by this styling migration.
