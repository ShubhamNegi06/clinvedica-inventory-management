"use client";

/**
 * Structured key:value filtering against a sample's custom_fields —
 * e.g. picking "Tumor %" and typing "60" filters to samples whose
 * Tumor % field contains "60" (matches ">60%"). This replaced an
 * earlier freeform tags feature that didn't match what was actually
 * requested: filtering on a SPECIFIC template field's value, not an
 * arbitrary label attached to a sample.
 */
import { useState } from "react";
import type { FieldDefinition, FieldFilter } from "@/lib/types";

export function FieldFilterInput({
  fields,
  filters,
  onChange,
}: {
  fields: FieldDefinition[];
  filters: FieldFilter[];
  onChange: (filters: FieldFilter[]) => void;
}) {
  const [selectedKey, setSelectedKey] = useState(fields[0]?.field_key ?? "");
  const [value, setValue] = useState("");

  function addFilter() {
    if (!selectedKey || !value.trim()) return;
    // Replace any existing filter on the same field rather than stacking
    // duplicates for the same key.
    const next = filters.filter((f) => f.field_key !== selectedKey);
    onChange([...next, { field_key: selectedKey, value: value.trim() }]);
    setValue("");
  }

  function fieldLabel(key: string): string {
    return fields.find((f) => f.field_key === key)?.field_label ?? key;
  }

  return (
    <div>
      <div className="flex gap-2">
        <select
          value={selectedKey}
          onChange={(e) => setSelectedKey(e.target.value)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        >
          {fields.map((f) => (
            <option key={f.field_key} value={f.field_key}>
              {f.field_label}
            </option>
          ))}
        </select>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addFilter())}
          placeholder="Value contains…"
          className="flex-1 rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        <button
          type="button"
          onClick={addFilter}
          className="rounded-lg border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Add Filter
        </button>
      </div>

      {filters.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {filters.map((f) => (
            <span
              key={f.field_key}
              className="flex items-center gap-1.5 rounded-full bg-peach-50 px-3 py-1 text-xs font-medium text-brand"
            >
              {fieldLabel(f.field_key)}: {f.value}
              <button
                onClick={() => onChange(filters.filter((x) => x.field_key !== f.field_key))}
                className="text-brand/60 hover:text-brand"
                aria-label={`Remove filter ${fieldLabel(f.field_key)}`}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
