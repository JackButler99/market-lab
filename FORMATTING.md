# Code formatting and line wrapping

The active frontend source and backend Python source are formatted in this update. Tailwind class lists are wrapped and indented in JSX/template literals; utility tokens are preserved. Python statements and SQL string literals are split across readable lines without changing their values.

## Apply

This patch expects the Tailwind migration update to be installed.

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-formatting.patch
git apply signal-formatting.patch
cd frontend
npx tsc --noEmit
npm run dev
```

## Keep future edits tidy

Install the project-local frontend formatter:

```bat
cd /d "G:\React porject\market-lab\frontend"
npm install -D prettier
npx prettier --write .
```

This also formats JSON, documentation and unused legacy CSS in your current local checkout. Those files are not replaced by the patch, so your locally upgraded package versions and any prior hover CSS are preserved. Generated dependencies, build output, data and package-lock.json are ignored.

Install the Python formatter (preferably in your existing development virtual environment):

```bat
cd /d "G:\React porject\market-lab"
python -m pip install black
python -m black backend
```

On Windows, use py instead of python if needed. Black is a development tool only; the backend still has no third-party runtime dependency.

## Editor integration

VS Code workspace settings enable format-on-save and bounded visual wrapping at 100 columns. Install the Prettier extension (esbenp.prettier-vscode) and Black Formatter extension (ms-python.black-formatter). Open market-lab as your workspace so the root configuration is found.

- Frontend: 2-space indentation, semicolons, double quotes, approximately 100 columns.
- Backend: 4-space indentation and Black with a 100-column target.
- Files use LF newlines; EditorConfig is included.
- Visual wrapping handles unusual long tokens that cannot safely be split. Formatter printWidth is a target, not an absolute limit.
- Prettier preserves existing multiline template-literal content. When adding Tailwind classes, keep each utility token intact and wrap between tokens.

Checks:

```bat
cd frontend
npx prettier --check .
npx tsc --noEmit
cd ..
python -m black --check backend
```

The initial patch was checked with Prettier, Black and TypeScript. Python's syntax tree before and after formatting was compared to ensure unchanged behavior. Formatting does not alter database schemas, API endpoints, forecasting logic or model parameters. Browser visual QA was unavailable.
