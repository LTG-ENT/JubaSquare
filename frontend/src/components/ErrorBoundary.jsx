import React from "react";
import { AlertTriangle } from "lucide-react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Uncaught UI error:", error, info);
  }
  reset = () => this.setState({ hasError: false, error: null });
  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 text-center">
        <AlertTriangle className="w-14 h-14 text-[#C84B31]" />
        <h1 className="font-display font-bold text-2xl text-[var(--js-text)] mt-4">Something went wrong</h1>
        <p className="text-sm text-[var(--js-text-secondary)] mt-2 max-w-md">
          An unexpected error occurred. Please refresh the page. If it persists, contact support.
        </p>
        <div className="mt-6 flex gap-3">
          <button onClick={() => { this.reset(); window.location.reload(); }}
            className="bg-[#C84B31] hover:bg-[#A83A23] text-white font-semibold px-5 py-2.5 rounded-xl text-sm">
            Refresh page
          </button>
          {/* Plain <a> instead of <Link>: ErrorBoundary is rendered OUTSIDE
              <BrowserRouter>, so a router-aware <Link> would itself crash
              with "Cannot destructure property 'basename' of useContext(...)". */}
          <a href="/" onClick={this.reset}
            className="bg-white border border-[var(--js-border)] hover:bg-[var(--js-subtle)] text-[var(--js-text)] font-semibold px-5 py-2.5 rounded-xl text-sm">
            Go home
          </a>
        </div>
      </div>
    );
  }
}
