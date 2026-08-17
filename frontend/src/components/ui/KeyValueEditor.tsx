import { useState, type ReactNode } from "react";
import { Button } from "./Button";
import { Input } from "./Input";
import type { KeyValue } from "../../types/api";

type Props = {
  items: KeyValue[];
  onChange: (items: KeyValue[]) => void;
  readOnly?: boolean;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
  suggestions?: string[];
};

export function KeyValueEditor({
  items,
  onChange,
  readOnly = false,
  keyPlaceholder = "Key",
  valuePlaceholder = "Value",
  suggestions = [],
}: Props) {
  const rows =
    items.length === 0
      ? [{ key: "", value: "", enabled: true }]
      : items;

  function update(index: number, patch: Partial<KeyValue>) {
    const next = rows.map((row, i) => (i === index ? { ...row, ...patch } : row));
    const cleaned = next.filter(
      (row, i) =>
        row.key.trim() ||
        row.value.trim() ||
        i === next.length - 1,
    );
    if (
      cleaned.length === 0 ||
      cleaned[cleaned.length - 1].key ||
      cleaned[cleaned.length - 1].value
    ) {
      cleaned.push({ key: "", value: "", enabled: true });
    }
    onChange(
      cleaned.filter(
        (row, i) =>
          i === cleaned.length - 1 || row.key.trim() || row.value.trim(),
      ),
    );
  }

  function remove(index: number) {
    const next = rows.filter((_, i) => i !== index);
    onChange(next.length ? next : [{ key: "", value: "", enabled: true }]);
  }

  return (
    <div className="kv-editor">
      <div className="kv-header">
        <span>Enabled</span>
        <span>Key</span>
        <span>Value</span>
        <span />
      </div>
      {rows.map((row, index) => (
        <div className="kv-row" key={index}>
          <input
            type="checkbox"
            checked={row.enabled}
            disabled={readOnly}
            aria-label={`Enable ${row.key || "row"}`}
            onChange={(e) => update(index, { enabled: e.target.checked })}
          />
          <Input
            list={suggestions.length ? "kv-suggestions" : undefined}
            value={row.key}
            placeholder={keyPlaceholder}
            readOnly={readOnly}
            onChange={(e) => update(index, { key: e.target.value })}
          />
          <Input
            value={row.value}
            placeholder={valuePlaceholder}
            readOnly={readOnly}
            onChange={(e) => update(index, { value: e.target.value })}
          />
          {!readOnly ? (
            <Button
              variant="ghost"
              size="sm"
              aria-label="Remove row"
              onClick={() => remove(index)}
              disabled={!row.key && !row.value && rows.length === 1}
            >
              ✕
            </Button>
          ) : (
            <span />
          )}
        </div>
      ))}
      {suggestions.length ? (
        <datalist id="kv-suggestions">
          {suggestions.map((item) => (
            <option key={item} value={item} />
          ))}
        </datalist>
      ) : null}
    </div>
  );
}

export function CodeBlock({
  value,
  language = "text",
  empty = "No content",
}: {
  value: string | null | undefined;
  language?: string;
  empty?: string;
}) {
  if (!value) return <div className="code-empty">{empty}</div>;
  let display = value;
  if (language === "json") {
    try {
      display = JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      display = value;
    }
  }
  return (
    <pre className={`code-block lang-${language}`}>
      <code>{display}</code>
    </pre>
  );
}

export function Tooltip({
  content,
  children,
}: {
  content: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="tooltip-wrap"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open ? <span className="tooltip">{content}</span> : null}
    </span>
  );
}
