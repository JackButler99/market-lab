import { twMerge } from "tailwind-merge";
import type { ComponentPropsWithRef, HTMLAttributes, ReactNode } from "react";

// Reusable primitives: change shared button and panel appearance here.
const buttonBase = `
  inline-flex items-center justify-center gap-2 rounded-md text-xs
  transition-[transform,background-color,border-color,color,box-shadow] duration-200
  cursor-pointer focus-visible:outline-2 focus-visible:outline-accent
  focus-visible:outline-offset-4 disabled:opacity-50 disabled:cursor-not-allowed
  enabled:active:translate-y-px enabled:active:scale-[.98] motion-reduce:transition-none
  motion-reduce:transform-none
`;
const buttonColors = {
  secondary: `
    border border-[#34414b] bg-[#19222a] text-[#d7e0e7] enabled:hover:bg-[#293844]
    enabled:hover:border-[#728773] enabled:hover:text-white enabled:hover:-translate-y-0.5
    enabled:hover:shadow-lg
  `,
  primary: `
    border border-accent bg-accent text-[#152114] font-semibold enabled:hover:bg-[#ccff91]
    enabled:hover:border-[#d8ffad] enabled:hover:-translate-y-0.5
    enabled:hover:shadow-[0_6px_20px_#b9f2752e]
  `,
  ghost: `
    border border-transparent bg-transparent text-muted enabled:hover:text-accent
    enabled:hover:bg-white/5
  `,
};
export function Button({
  variant = "secondary",
  compact = false,
  className = "",
  ...props
}: ComponentPropsWithRef<"button"> & { variant?: keyof typeof buttonColors; compact?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      className={twMerge(
        buttonBase,
        buttonColors[variant],
        compact ? "px-2.5 py-1.5" : "px-4 py-2.5",
        className,
      )}
    />
  );
}
export function Panel({ className = "", ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      {...props}
      className={twMerge(
        "rounded-[10px] border border-line bg-surface p-[23px] max-[650px]:p-[17px]",
        className,
      )}
    />
  );
}
export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="text-[9px] font-semibold tracking-[1.8px] text-[#a1b29e]">{children}</div>;
}
export function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="shrink-0 rounded border border-[#3b4850] px-2 py-1 text-[9px] text-[#aab6bc]">
      {children}
    </span>
  );
}
export const selectClass = `
  mt-2 block w-full rounded-md border border-[#39454f] bg-[#1a252e] px-2.5 py-3 text-xs
  tracking-normal text-ink focus-visible:outline-2 focus-visible:outline-accent
  focus-visible:outline-offset-2 disabled:opacity-50
`;
export const labelClass = "my-[18px] block text-[10px] tracking-widest text-muted";
export const hintClass = "text-xs leading-7 text-muted";
export const tableClass = `
  mt-6 w-full border-collapse whitespace-nowrap text-left [&_th]:px-3 [&_th]:py-4
  [&_th]:text-[10px] [&_th]:font-normal [&_th]:tracking-widest [&_th]:text-muted [&_td]:px-3
  [&_td]:py-4 [&_td]:text-xs [&_td]:text-[#c7d0d7] [&_th]:border-b [&_th]:border-line
  [&_td]:border-b [&_td]:border-line
`;
