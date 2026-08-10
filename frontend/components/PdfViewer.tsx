"use client";

import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// pdf.js needs its worker script — loaded from a CDN matching the
// installed pdfjs-dist version rather than bundled, to avoid Next.js
// webpack worker-loading complications.
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export function PdfViewer({ url, fileName }: { url: string; fileName: string }) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <p className="truncate text-sm font-medium text-gray-700">{fileName}</p>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-medium text-brand hover:underline"
        >
          Open in new tab
        </a>
      </div>

      {error ? (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : (
        <div className="flex flex-col items-center">
          <Document
            file={url}
            onLoadSuccess={({ numPages: n }) => setNumPages(n)}
            onLoadError={() => setError("Could not render this PDF. Try opening it in a new tab instead.")}
            loading={<p className="py-8 text-sm text-gray-400">Loading PDF…</p>}
          >
            <Page pageNumber={pageNumber} width={600} />
          </Document>

          {numPages > 1 && (
            <div className="mt-3 flex items-center gap-3">
              <button
                disabled={pageNumber <= 1}
                onClick={() => setPageNumber((p) => p - 1)}
                className="rounded-lg border border-gray-200 px-3 py-1 text-xs disabled:opacity-40"
              >
                Prev
              </button>
              <span className="text-xs text-gray-500">
                Page {pageNumber} of {numPages}
              </span>
              <button
                disabled={pageNumber >= numPages}
                onClick={() => setPageNumber((p) => p + 1)}
                className="rounded-lg border border-gray-200 px-3 py-1 text-xs disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
