import { reportUrl } from "../api";

export default function ReportButtons({ id }: { id?: number }) {
  if (!id) return null;
  return (
    <div className="flex flex-wrap gap-2">
      <a className="btn btn-ghost text-sm" href={reportUrl(id, "pdf")} target="_blank" rel="noopener">⬇️ PDF-Bericht</a>
      <a className="btn btn-ghost text-sm" href={reportUrl(id, "csv")} target="_blank" rel="noopener">⬇️ CSV</a>
      <a className="btn btn-ghost text-sm" href={reportUrl(id, "json")} target="_blank" rel="noopener">⬇️ JSON</a>
    </div>
  );
}
