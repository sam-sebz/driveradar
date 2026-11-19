import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useUpload } from "../api/hooks";
import { EligibilityBadge, MatchBadge } from "../components/Badges";
import { ErrorBox } from "../components/Layout";

const ACCEPT = ".pdf,.docx,.xlsx";
const MAX_BYTES = 10 * 1024 * 1024;

export function UploadPage() {
  const upload = useUpload();
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const pick = (f: File | undefined) => {
    setLocalError(null);
    if (!f) return;
    if (!/\.(pdf|docx|xlsx)$/i.test(f.name)) {
      setLocalError("Only PDF, DOCX and XLSX files are supported.");
      return;
    }
    if (f.size > MAX_BYTES) {
      setLocalError("File is larger than 10 MB.");
      return;
    }
    setFile(f);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files[0]);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (file) upload.mutate({ file });
    else if (text.trim()) upload.mutate({ text });
    else setLocalError("Choose a file or paste the notice text.");
  };

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold">Upload a placement notice</h1>
      <form onSubmit={submit} className="card space-y-4">
        <div
          role="button"
          tabIndex={0}
          aria-label="Drop a file here or click to choose"
          onClick={() => input.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center ${
            dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300"
          }`}
        >
          <p className="font-medium">{file ? file.name : "Drag and drop a PDF, DOCX or XLSX"}</p>
          <p className="text-sm text-slate-500">or click to choose (max 10 MB)</p>
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            className="hidden"
            data-testid="file-input"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </div>
        <div>
          <label className="label" htmlFor="paste">
            Or paste the notice text
          </label>
          <textarea
            id="paste"
            rows={6}
            className="input font-mono"
            value={text}
            disabled={file !== null}
            onChange={(e) => setText(e.target.value)}
            placeholder="Company: ...&#10;Role: ...&#10;Eligibility: ..."
          />
        </div>
        {localError && (
          <p role="alert" className="text-sm text-rose-700">
            {localError}
          </p>
        )}
        <ErrorBox error={upload.error} />
        <div className="flex gap-2">
          <button type="submit" className="btn" disabled={upload.isPending}>
            {upload.isPending ? "Reading notice..." : "Analyse notice"}
          </button>
          {file && (
            <button type="button" className="btn-secondary" onClick={() => setFile(null)}>
              Clear file
            </button>
          )}
        </div>
      </form>

      {upload.data && (
        <div className="card space-y-3">
          <h2 className="font-semibold">
            Found {upload.data.drives.length} role{upload.data.drives.length === 1 ? "" : "s"}
          </h2>
          <ul className="divide-y divide-slate-100">
            {upload.data.drives.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-3 py-2">
                <Link to={`/drives/${d.id}`} className="font-medium text-indigo-700 hover:underline">
                  {d.info.company ?? "Unknown company"}: {d.info.role ?? "role not stated"}
                </Link>
                <EligibilityBadge value={d.eligibility} />
                <MatchBadge score={d.match_score} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
