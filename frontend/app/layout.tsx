import "./tailwind.css";
export const metadata = {
  title: "Signal / Forecast Research Lab",
  description: "Local market data and forecasting experiments",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="m-0 bg-canvas font-sans text-sm text-ink antialiased">{children}</body>
    </html>
  );
}
