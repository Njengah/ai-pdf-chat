import { useEffect, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import workerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { fetchDocumentPdf } from "./api";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

type Props = {
  documentId: string;
  filename: string;
  page: number;
  onClose: () => void;
  onPageChange: (page: number) => void;
};

export default function PdfViewer({
  documentId,
  filename,
  page,
  onClose,
  onPageChange,
}: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDocumentPdf(documentId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load PDF");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  const safePage = Math.min(Math.max(page, 1), numPages || page || 1);

  return (
    <aside className="pdf-viewer">
      <header className="pdf-viewer-top">
        <div>
          <strong>{filename}</strong>
          <small>
            Page {safePage}
            {numPages ? ` of ${numPages}` : ""}
          </small>
        </div>
        <div className="pdf-viewer-controls">
          <button
            type="button"
            className="btn-text sm"
            disabled={safePage <= 1}
            onClick={() => onPageChange(safePage - 1)}
          >
            Prev
          </button>
          <button
            type="button"
            className="btn-text sm"
            disabled={numPages > 0 && safePage >= numPages}
            onClick={() => onPageChange(safePage + 1)}
          >
            Next
          </button>
          <button type="button" className="btn-icon" onClick={onClose} aria-label="Close viewer">
            ×
          </button>
        </div>
      </header>

      <div className="pdf-viewer-body">
        {loading && <p className="muted">Loading PDF…</p>}
        {error && <p className="error">{error}</p>}
        {url && !error && (
          <Document
            file={url}
            loading={<p className="muted">Rendering…</p>}
            onLoadSuccess={(info) => setNumPages(info.numPages)}
            onLoadError={() => setError("Could not render this PDF")}
          >
            <Page
              pageNumber={safePage}
              width={360}
              renderAnnotationLayer
              renderTextLayer
            />
          </Document>
        )}
      </div>
    </aside>
  );
}
