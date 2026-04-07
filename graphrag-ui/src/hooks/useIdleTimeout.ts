import { useEffect, useRef, useCallback } from "react";

const DEFAULT_TIMEOUT_MS = 60 * 60 * 1000; // 1 hour

/**
 * Monitors user activity and clears the session after a period of inactivity.
 * Resets the timer on mouse, keyboard, scroll, and touch events.
 */
export function useIdleTimeout(timeoutMs: number = DEFAULT_TIMEOUT_MS) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleTimeout = useCallback(() => {
    const creds = sessionStorage.getItem("creds");
    if (!creds) return; // Not logged in, nothing to do

    sessionStorage.clear();
    alert("Session expired due to inactivity. Please log in again.");
    window.location.href = "/";
  }, []);

  const resetTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    // Only set timer if user is logged in
    if (sessionStorage.getItem("creds")) {
      timerRef.current = setTimeout(handleTimeout, timeoutMs);
    }
  }, [handleTimeout, timeoutMs]);

  useEffect(() => {
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"];

    events.forEach((event) => window.addEventListener(event, resetTimer));
    resetTimer(); // Start the timer

    return () => {
      events.forEach((event) => window.removeEventListener(event, resetTimer));
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [resetTimer]);
}
