"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "./ui";
const KEY = "signal-tutorial-v1";
const steps = [
  {
    tab: "Overview",
    target: '[data-tour="research-mode"]',
    title: "Welcome to your research lab",
    text:
      "Learn how to select data, run a forecast and evaluate it. Unsynced seed prices are " +
      "synthetic examples, not live market quotes.",
    task: "This tour explains the controls. You can still use the page while it is open.",
  },
  {
    tab: "Overview",
    target: '[data-tour="assets"]',
    title: "1. Choose a market",
    text:
      "Select an asset card to load its stored price series. Check its source and “as of” " +
      "date before interpreting the chart.",
    task: "Try selecting AAPL. Each asset has its own dataset.",
  },
  {
    tab: "Overview",
    target: '[data-tour="builder"]',
    title: "2. Configure your experiment",
    text:
      "Start with Rolling log-linear trend and a horizon of 7 observations. The naive model " +
      "simply repeats the last known price.",
    task: "Seven observations means seven rows in your series, not necessarily seven calendar days.",
  },
  {
    tab: "Overview",
    target: '[data-tour="run"]',
    title: "3. Run the model",
    text:
      "Click Run experiment when the API is connected. Python tests historical predictions " +
      "using earlier observations, creates a forecast, and saves the run.",
    task: "You can run it now, or continue the tour. The tutorial never runs experiments for you.",
  },
  {
    tab: "Overview",
    target: '[data-tour="chart"]',
    title: "4. Read the forecast",
    text:
      "Green shows historical closes. The dashed purple line shows model predictions. Purple " +
      "shading is an exploratory residual band, not a guaranteed range.",
    task: "No forecast yet? Return to the previous step and run an experiment.",
  },
  {
    tab: "Overview",
    target: '[data-tour="metrics"]',
    title: "5. Compare against a baseline",
    text:
      "Lower MAE means lower historical error. A positive “Vs. baseline” means the model " +
      "reduced error compared with repeating the latest price.",
    task:
      "Example: model MAE 4 versus baseline MAE 5 means 20% lower error. Compare the same " +
      "asset, dataset and horizon.",
  },
  {
    tab: "Experiments",
    target: '[data-tour="registry"]',
    title: "6. Keep an experiment record",
    text: "The registry links new runs to an immutable dataset snapshot and model version.",
    task: "Replay reruns a saved dataset, model and horizon. Legacy runs without dataset IDs cannot be replayed.",
  },
  {
    tab: "Data pipeline",
    target: '[data-tour="import"]',
    title: "7. Bring your own observations",
    text:
      "Choose a destination asset, then import a CSV with date,close headers and at least " +
      "100 unique ISO dates. Close values must be finite and positive.",
    task:
      "Import replaces the selected asset’s whole price series. Use matching asset data and " +
      "consistent frequency. No upload is required to finish this tour.",
  },
  {
    tab: "Fundamentals",
    target: '[data-tour="fundamentals"]',
    title: "8. Read evidence with context",
    text:
      "Daily API sync is available for AAPL, MSFT, EURUSD and BTCUSD. " +
      "SEC annual fundamentals are available for AAPL/MSFT, macro indicators for EURUSD, and network metrics for BTCUSD. LLM analysis and automatic retraining remain planned.",
    task: "Choose Stocks, EURUSD Macro or BTC Network. Sync fundamentals, then try Beginner / Intermediate / Expert. Insights follow the selected snapshot and annual period. Open source evidence and check stale labels before drawing conclusions.",
  },
  {
    tab: "Overview",
    target: '[data-tour="builder"]',
    title: "Ready for your first experiment",
    text:
      "Select AAPL, choose a 7-observation horizon, run a model and compare its MAE with the " +
      "baseline. Then repeat using your own CSV.",
    task: "Replay this guide any time with Start tutorial. Results are experimental research outputs.",
  },
];
export default function ResearchTutorial({ onNavigate }: { onNavigate: (tab: string) => void }) {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [intro, setIntro] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const navigate = useRef(onNavigate);
  useEffect(() => {
    navigate.current = onNavigate;
  }, [onNavigate]);
  useEffect(() => {
    try {
      setIntro(!localStorage.getItem(KEY));
    } catch {
      setIntro(true);
    }
  }, []);
  const step = steps[index];
  function remember(value: string) {
    try {
      localStorage.setItem(KEY, value);
    } catch {
      /* Storage may be unavailable in private browsing. */
    }
  }
  function close(value: string) {
    remember(value);
    setOpen(false);
    setIntro(false);
    trigger.current?.focus();
  }
  function start() {
    setIntro(false);
    setIndex(0);
    setOpen(true);
  }
  useEffect(() => {
    if (!open) return;
    navigate.current(step.tab);
    const timer = window.setTimeout(() => {
      document
        .querySelectorAll("[data-tour-active]")
        .forEach((e) => e.removeAttribute("data-tour-active"));
      const target = document.querySelector(step.target);
      target?.setAttribute("data-tour-active", "true");
      target?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "center",
      });
      heading.current?.focus({ preventScroll: true });
    }, 100);
    return () => {
      window.clearTimeout(timer);
      document
        .querySelectorAll("[data-tour-active]")
        .forEach((e) => e.removeAttribute("data-tour-active"));
    };
  }, [open, index, step]);
  useEffect(() => {
    if (!open) return;
    function key(e: KeyboardEvent) {
      if (e.key === "Escape") close("dismissed");
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open]);
  return (
    <>
      <Button
        ref={trigger}
        variant="primary"
        onClick={start}
        className="
          fixed right-[26px] bottom-[22px] z-40 rounded-full px-5 py-3 text-[13px] shadow-xl
          max-[650px]:right-4 max-[650px]:bottom-4
        "
      >
        ⓘ Start tutorial
      </Button>
      {intro && !open && (
        <section
          className="
            my-[22px] flex items-center gap-3.5 rounded-[10px] border border-[#4e6543]
            bg-[#1c2a23] p-[18px] max-[650px]:flex-wrap
          "
          aria-label="Tutorial invitation"
        >
          <div className="flex-1 max-[650px]:basis-full">
            <strong className="text-[15px]">New to Signal?</strong>
            <p className="mt-1.5 text-[13px] leading-6 text-[#b0c0b8]">
              Take a short tour of data, forecasts and model evaluation.
            </p>
          </div>
          <Button
            onClick={() => {
              remember("dismissed");
              setIntro(false);
            }}
          >
            Not now
          </Button>
          <Button onClick={start}>Take the tour ↗</Button>
        </section>
      )}
      {open && (
        <section
          className="
            fixed right-[26px] bottom-[78px] z-50 max-h-[70vh] w-[390px]
            max-w-[calc(100vw_-_32px)] overflow-auto rounded-[14px] border border-[#647c53]
            bg-elevated p-[22px] shadow-[0_18px_65px_#0009] max-[650px]:right-4
            max-[650px]:bottom-[75px] max-[650px]:max-h-[52vh] max-[650px]:p-[18px]
          "
          role="region"
          aria-label="Research tutorial"
        >
          <div className="flex items-center justify-between text-[10px] tracking-[1.5px] text-accent">
            <span>
              QUICK START · {index + 1} / {steps.length}
            </span>
            <Button
              variant="ghost"
              compact
              aria-label="Close tutorial"
              onClick={() => close("dismissed")}
              className="text-xl hover:rotate-[8deg] motion-reduce:transform-none"
            >
              ×
            </Button>
          </div>
          <progress
            className="mt-2.5 block h-1 w-full accent-accent"
            max={steps.length}
            value={index + 1}
            aria-label="Tutorial progress"
          />
          <h2
            ref={heading}
            tabIndex={-1}
            className="
              mt-[21px] mb-3 text-xl leading-snug tracking-tight text-[#eff5f1] focus:outline-none
              max-[650px]:text-lg
            "
          >
            {step.title}
          </h2>
          <p className="mb-4 text-sm leading-7 text-[#b8c7d1] max-[650px]:text-[13px]">
            {step.text}
          </p>
          <div className="rounded-md bg-[#26352d] p-[13px] text-xs leading-6 text-[#c5dbba]">
            {step.task}
          </div>
          <div className="mt-5 flex items-center gap-2">
            <Button variant="ghost" className="mr-auto px-0" onClick={() => close("dismissed")}>
              Skip tour
            </Button>
            <Button disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
              Back
            </Button>
            <Button
              variant="primary"
              onClick={() =>
                index === steps.length - 1 ? close("completed") : setIndex((i) => i + 1)
              }
            >
              {index === steps.length - 1 ? "Finish" : "Next →"}
            </Button>
          </div>
        </section>
      )}
    </>
  );
}
