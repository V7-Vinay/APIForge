import type { InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes, ReactNode } from "react";

type FieldProps = {
  label?: string;
  hint?: string;
  error?: string;
  className?: string;
  children: ReactNode;
  htmlFor?: string;
};

export function Field({ label, hint, error, className = "", children, htmlFor }: FieldProps) {
  return (
    <label className={`field ${className}`.trim()} htmlFor={htmlFor}>
      {label ? <span className="field-label">{label}</span> : null}
      {children}
      {hint && !error ? <span className="field-hint">{hint}</span> : null}
      {error ? <span className="field-error">{error}</span> : null}
    </label>
  );
}

export function Input({ className = "", ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${className}`.trim()} {...rest} />;
}

export function Textarea({
  className = "",
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`input textarea ${className}`.trim()} {...rest} />;
}

export function Select({
  className = "",
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={`input select ${className}`.trim()} {...rest}>
      {children}
    </select>
  );
}
