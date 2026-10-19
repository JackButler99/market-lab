// Production uses our same-origin server proxy. No service credential enters client JS.
export const PUBLIC_READ_ONLY =
  process.env.NODE_ENV === "production" || process.env.NEXT_PUBLIC_READ_ONLY === "true";
export const API_BASE = PUBLIC_READ_ONLY
  ? ""
  : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
