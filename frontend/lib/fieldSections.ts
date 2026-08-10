/**
 * Groups a flat FieldDefinition[] (as returned by GET /field-definitions)
 * into ordered sections for form/detail rendering. Mirrors v1's
 * lib/fieldOrder.ts / lib/sections.ts split, consolidated into one file
 * since the backend is now the single source of truth for ordering
 * (display_order + section), not the frontend.
 */
import { FieldDefinition, SECTION_LABELS, SECTION_ORDER } from "./types";

export interface FieldSection {
  key: string;
  label: string;
  fields: FieldDefinition[];
}

export function groupFieldsBySections(fields: FieldDefinition[]): FieldSection[] {
  const bySection = new Map<string, FieldDefinition[]>();
  for (const field of fields) {
    const list = bySection.get(field.section) ?? [];
    list.push(field);
    bySection.set(field.section, list);
  }

  const sections: FieldSection[] = [];
  for (const key of SECTION_ORDER) {
    const sectionFields = (bySection.get(key) ?? []).sort((a, b) => a.display_order - b.display_order);
    if (sectionFields.length > 0) {
      sections.push({ key, label: SECTION_LABELS[key] ?? key, fields: sectionFields });
    }
  }
  return sections;
}

/** kebab-case sanitization for any ad-hoc field keys entered client-side (bulk ingest preview, etc.) */
export function toKebabCase(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
