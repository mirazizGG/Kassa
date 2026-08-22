import React, { useEffect, useState } from "react";
import { Minus, Square, Copy, X } from "lucide-react";

const isElectron =
  typeof window !== "undefined" && window.electronAPI?.isElectron;

const TitleBar = () => {
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    if (!isElectron) return;
    return window.electronAPI.onMaximizedChange(setIsMaximized);
  }, []);

  if (!isElectron) return null;

  return (
    <div
      className="flex h-9 shrink-0 select-none items-center justify-between bg-gradient-to-r from-indigo-600 to-violet-600 pl-3 text-white shadow-sm"
      style={{ WebkitAppRegion: "drag" }}
    >
      <div className="flex items-center gap-2 text-sm font-semibold tracking-wide">
        <div className="flex h-5 w-5 items-center justify-center rounded bg-white/15">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-3 w-3"
          >
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
        </div>
        SmartKassa
      </div>

      <div
        className="flex h-full items-stretch"
        style={{ WebkitAppRegion: "no-drag" }}
      >
        <button
          type="button"
          aria-label="Yig'ish"
          onClick={() => window.electronAPI.minimize()}
          className="flex w-11 items-center justify-center transition-colors hover:bg-white/15"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label={isMaximized ? "Kichraytirish" : "Kattalashtirish"}
          onClick={() => window.electronAPI.maximize()}
          className="flex w-11 items-center justify-center transition-colors hover:bg-white/15"
        >
          {isMaximized ? (
            <Copy className="h-3 w-3 scale-x-[-1]" />
          ) : (
            <Square className="h-3 w-3" />
          )}
        </button>
        <button
          type="button"
          aria-label="Yopish"
          onClick={() => window.electronAPI.close()}
          className="flex w-11 items-center justify-center transition-colors hover:bg-red-500"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default TitleBar;
export { isElectron };
