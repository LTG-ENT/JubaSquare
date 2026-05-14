import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * Optimized polling hook with:
 * - Visibility-based polling (pauses when tab is hidden)
 * - Error handling with exponential backoff
 * - Automatic cleanup
 * 
 * @param {Function} callback - Function to call on each poll
 * @param {number} interval - Polling interval in milliseconds (default: 15000)
 * @param {Object} options - Additional options
 * @param {boolean} options.enabled - Whether polling is enabled (default: true)
 * @param {boolean} options.runOnMount - Whether to run immediately on mount (default: true)
 * @param {number} options.maxBackoff - Maximum backoff time in ms (default: 60000)
 */
export function useOptimizedPolling(callback, interval = 15000, options = {}) {
  const {
    enabled = true,
    runOnMount = true,
    maxBackoff = 60000,
  } = options;

  const callbackRef = useRef(callback);
  const intervalRef = useRef(null);
  const backoffRef = useRef(interval);
  const isVisibleRef = useRef(true);
  const errorCountRef = useRef(0);

  // Keep callback ref up to date
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // Wrapped callback with error handling and backoff
  const wrappedCallback = useCallback(async () => {
    // Don't poll if tab is hidden
    if (!isVisibleRef.current) {
      return;
    }

    try {
      await callbackRef.current();
      // Reset backoff on success
      if (errorCountRef.current > 0) {
        errorCountRef.current = 0;
        backoffRef.current = interval;
      }
    } catch (error) {
      // Exponential backoff on error
      errorCountRef.current++;
      const newBackoff = Math.min(
        interval * Math.pow(2, errorCountRef.current),
        maxBackoff
      );
      backoffRef.current = newBackoff;
      console.warn(`Polling error (attempt ${errorCountRef.current}), backing off to ${newBackoff}ms:`, error);
    }
  }, [interval, maxBackoff]);

  // Handle visibility change
  useEffect(() => {
    const handleVisibilityChange = () => {
      isVisibleRef.current = !document.hidden;
      
      // Resume polling immediately when tab becomes visible
      if (isVisibleRef.current && enabled) {
        wrappedCallback();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [wrappedCallback, enabled]);

  // Main polling effect
  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Run immediately on mount if requested
    if (runOnMount) {
      wrappedCallback();
    }

    // Set up interval with current backoff
    const startPolling = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      intervalRef.current = setInterval(wrappedCallback, backoffRef.current);
    };

    startPolling();

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, runOnMount, wrappedCallback]);

  // Return a manual trigger function
  const trigger = useCallback(() => {
    wrappedCallback();
  }, [wrappedCallback]);

  return { trigger };
}

/**
 * Simple hook to detect if page is visible
 */
export function usePageVisibility() {
  const [isVisible, setIsVisible] = useState(!document.hidden);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setIsVisible(!document.hidden);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  return isVisible;
}
