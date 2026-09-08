/**
 * Central API configuration for BHARATSHIELD frontend.
 *
 * VITE_API_BASE must be set to the bare backend origin on Vercel (e.g.
 * https://bharat-shield-ckq5.onrender.com -- no trailing slash, no /api suffix).
 *
 * This module normalises whatever value is provided and appends /api once,
 * so callers never have to worry about double-/api or missing-/api bugs.
 */
const RAW_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Strip accidental trailing slashes AND any accidental /api suffix so we
// never build a URL like https://...onrender.com/api/api/screening/batch.
const CLEAN_ORIGIN = RAW_BASE.replace(/\/+$/, "").replace(/\/api$/, "");

export const API_BASE_URL = `${CLEAN_ORIGIN}/api`;
