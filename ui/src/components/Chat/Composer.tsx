import { useRef, useState } from "react";
import { api } from "../../api";
import { Btn, ErrorLine } from "../ui";

/** The message box, with the file drop that feeds the agents' upload intake. */
export default function Composer({
  disabled,
  onSent,
  onUploaded,
}: {
  disabled: boolean;
  onSent: (text: string) => Promise<void>;
  onUploaded: () => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState("");
  const file = useRef<HTMLInputElement>(null);

  const send = async () => {
    const t = text.trim();
    if (!t || disabled) return;
    setText("");
    setError(null);
    try {
      await onSent(t);
    } catch (e) {
      setText(t);
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setError(null);
    for (const f of Array.from(files)) {
      setUploading(f.name);
      try {
        await api.upload(f);
      } catch (e) {
        setError(`${f.name}: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
    setUploading("");
    await onUploaded();
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        void upload(e.dataTransfer.files);
      }}
      className={`rounded-lg border p-2 ${dragging ? "border-sky-500 bg-sky-950/30" : "border-slate-800 bg-slate-900/60"}`}
    >
      <textarea
        value={text}
        rows={2}
        disabled={disabled}
        placeholder={disabled ? "the agent is working…" : "Answer here — or drop a CSV, spreadsheet or document in"}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void send();
        }}
        className="w-full resize-none bg-transparent px-1 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none"
      />
      <div className="flex items-center gap-2">
        <input
          ref={file}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => void upload(e.target.files)}
        />
        <Btn kind="ghost" onClick={() => file.current?.click()} disabled={disabled}>
          {uploading ? `uploading ${uploading}…` : "Attach"}
        </Btn>
        <span className="text-[11px] text-slate-600">csv · tsv · json · xlsx · md · txt · pdf · docx</span>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-[11px] text-slate-600 sm:inline">⌘↵ to send</span>
          <Btn kind="primary" onClick={send} disabled={disabled || !text.trim()}>
            Send
          </Btn>
        </div>
      </div>
      <ErrorLine error={error} />
    </div>
  );
}
