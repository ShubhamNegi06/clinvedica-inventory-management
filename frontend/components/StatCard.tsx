import Link from "next/link";

/**
 * When `href` is provided, the whole card becomes a link to where that
 * number's underlying data actually lives (e.g. "Total Users" -> /users).
 * Without href it falls back to a plain non-interactive card — kept as
 * an option rather than always-required in case a future stat has
 * nowhere sensible to link to.
 */
export function StatCard({
  label,
  value,
  accent = false,
  href,
}: {
  label: string;
  value: number | string;
  accent?: boolean;
  href?: string;
}) {
  const content = (
    <>
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${accent ? "text-brand" : "text-gray-900"}`}>{value}</p>
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="block rounded-2xl border border-gray-100 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-md"
      >
        {content}
      </Link>
    );
  }

  return <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">{content}</div>;
}
