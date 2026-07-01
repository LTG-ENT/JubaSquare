import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import "@/i18n"; // Initialize i18n
import App from "@/App";
import { registerServiceWorker } from "@/lib/pwa";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Register the service worker after the app mounts (non-blocking)
if (typeof window !== "undefined") {
  window.addEventListener("load", () => {
    registerServiceWorker();
  });
}
