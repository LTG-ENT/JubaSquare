import { useState, forwardRef } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * A password <input> with a built-in eye/show-hide button.
 * Fully controlled. Use anywhere we take a password (login, signup, reset, change, admin user create).
 *
 * Props:
 *   value, onChange (function receiving raw string), label?, placeholder?, testId, autoComplete?,
 *   required?, minLength?, className? (extra classes on the input), initialShown? (defaults false),
 *   error? (optional error text below), inputClassName? (override default input class entirely),
 *   name?, id?, disabled?
 *
 * Rendered wrapper is a <div> with class "js-password-field".
 */
const PasswordInput = forwardRef(function PasswordInput(
  {
    value,
    onChange,
    label,
    placeholder,
    testId = "password-input",
    autoComplete = "current-password",
    required = false,
    minLength,
    className = "",
    inputClassName,
    initialShown = false,
    error,
    name,
    id,
    disabled = false,
    labelClassName,
  },
  ref
) {
  const [shown, setShown] = useState(!!initialShown);

  const baseInput =
    "w-full pr-10 px-3 py-2.5 rounded-xl border border-[var(--js-border)] bg-[var(--js-bg)] text-sm text-[var(--js-text)] focus:outline-none focus:border-[#1A1A1A] transition disabled:opacity-60 disabled:cursor-not-allowed";

  return (
    <div className={`js-password-field ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className={
            labelClassName ||
            "text-xs font-semibold uppercase tracking-wider text-[var(--js-text-secondary)] block mb-1.5"
          }
        >
          {label}
        </label>
      )}
      <div className="relative">
        <input
          ref={ref}
          id={id}
          name={name}
          type={shown ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          minLength={minLength}
          disabled={disabled}
          data-testid={testId}
          className={inputClassName || baseInput}
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          aria-label={shown ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full text-[var(--js-text-secondary)] hover:bg-[var(--js-subtle)] hover:text-[var(--js-text)] transition"
          data-testid={`${testId}-toggle`}
          tabIndex={-1}
        >
          {shown ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-[#C84B31]">{error}</p>}
    </div>
  );
});

export default PasswordInput;
