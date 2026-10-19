"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
export type ReadingLevel = "beginner" | "intermediate" | "expert";
const Context = createContext<{ level: ReadingLevel; setLevel: (value: ReadingLevel) => void }>({
  level: "beginner",
  setLevel: () => {},
});
export function InsightPreferences({ children }: { children: ReactNode }) {
  const [level, setLevel] = useState<ReadingLevel>("beginner");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try {
      const value = localStorage.getItem("market-lab-reading-level");
      if (["beginner", "intermediate", "expert"].includes(value || ""))
        setLevel(value as ReadingLevel);
    } catch {}
    setReady(true);
  }, []);
  useEffect(() => {
    if (ready) {
      try {
        localStorage.setItem("market-lab-reading-level", level);
      } catch {}
    }
  }, [level, ready]);
  return <Context.Provider value={{ level, setLevel }}>{children}</Context.Provider>;
}
export const useInsightPreferences = () => useContext(Context);
