import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";

// Locked view (Grace, 2026-07-27): the app should feel like an app, not a
// zoomable web page. The viewport meta handles the standalone PWA; iOS Safari
// TABS ignore user-scalable=no on purpose, so pinch-zoom is cancelled here via
// the WebKit-only gesture events (which is what actually works), and
// double-tap zoom via CSS touch-action. Scrolling is untouched — only zoom and
// the rubber-band pan go away.
for (const evt of ["gesturestart", "gesturechange", "gestureend"]) {
  document.addEventListener(evt, (e) => e.preventDefault(), { passive: false });
}
// two-finger pinch on elements that CSS touch-action can't cover
document.addEventListener("touchmove", (e) => {
  if (e.touches.length > 1) e.preventDefault();
}, { passive: false });

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
