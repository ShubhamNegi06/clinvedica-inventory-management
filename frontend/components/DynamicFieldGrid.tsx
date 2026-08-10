"use client";

/**
 * IMPORTANT: these components must stay at module scope, not be defined
 * inside a parent component's function body. Defining them inline causes
 * React to treat them as a brand-new component type on every parent
 * re-render, remounting every input and losing focus after each
 * keystroke — this bit the v1 build and cost real debugging time, so the
 * fix is preserved structurally here rather than left to be
 * accidentally reintroduced.
 */
import type { FieldDefinition } from "@/lib/types";
import { Field, TextInput, Select } from "./FormFields";

interface DynamicFieldGridProps {
  fields: FieldDefinition[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  autofilledKeys?: Set<string>;
}

export function DynamicFieldGrid({ fields, values, onChange, autofilledKeys }: DynamicFieldGridProps) {
  return (
    <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
      {fields.map((field) => (
        <Field
          key={field.field_key}
          label={
            autofilledKeys?.has(field.field_key)
              ? `${field.field_label} · Autofilled`
              : field.field_label
          }
        >
          <TextInput
            type={field.field_type === "number" ? "number" : field.field_type === "date" ? "date" : "text"}
            value={(values[field.field_key] as string) ?? ""}
            onChange={(e) => onChange(field.field_key, e.target.value)}
            className={autofilledKeys?.has(field.field_key) ? "border-amber-300 bg-amber-50/40" : ""}
          />
        </Field>
      ))}
    </div>
  );
}

interface SectionCardProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

export function SectionCard({ title, children, defaultOpen = true }: SectionCardProps) {
  return (
    <details open={defaultOpen} className="mb-4 rounded-2xl border border-gray-100 bg-white shadow-sm">
      <summary className="cursor-pointer select-none px-6 py-4 text-sm font-semibold text-gray-900">
        {title}
      </summary>
      <div className="border-t border-gray-100 px-6 py-5">{children}</div>
    </details>
  );
}
