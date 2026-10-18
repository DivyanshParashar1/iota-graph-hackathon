import { useRef, useState } from "react";
import { api } from "../../api";
import { Icon } from "../icons";
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
  const [drafting, setDrafting] = useState(false);
  const [draftNote, setDraftNote] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const send = async () => {
    const t = text.trim();
    if (!t || disabled) return;
    setText("");
    setError(null);
    setDraftNote(null);
    try {
      await onSent(t);
    } catch (e) {
      setText(t);
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // Demo only: ask the model for a plausible answer and put it in the box to edit; never sent automatically.
  const autofill = async () => {
    setDrafting(true);
    setError(null);
    try {
      const d = await api.autofill();
      setText(d.text);
      setDraftNote(d.note || "Demo answer drafted by the model.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDrafting(false);
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
      className={`border p-2 ${dragging ? "border-sky-400" : "border-line-strong focus-within:border-slate-400"}`}
    >
      <textarea
        value={text}
        rows={2}
        disabled={disabled || drafting}
        placeholder={drafting ? "drafting a demo answer…" : disabled ? "the agent is working…" : "Answer here — or drop a CSV, spreadsheet or document in"}
        onChange={(e) => {
          setText(e.target.value);
          if (!e.target.value) setDraftNote(null);
        }}
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
        <Btn kind="ghost" icon="sparkle" onClick={() => void autofill()} disabled={disabled || drafting}
             title="Demo only: draft a plausible answer to the agent's latest message. You can edit it before sending.">
          {drafting ? "Drafting…" : "Autofill"}
        </Btn>
        <span className="hidden text-[11px] text-slate-600 md:inline">csv · tsv · json · xlsx · md · txt · pdf · docx</span>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-[11px] text-slate-600 sm:inline">⌘↵ to send</span>
          <Btn kind="primary" onClick={send} disabled={disabled || !text.trim()}>
            Send
          </Btn>
        </div>
      </div>
      {draftNote && text && (
        <div className="mt-1.5 flex items-center gap-1.5 border-l border-violet-400 py-0.5 pl-2 text-[11.5px] text-muted">
          <Icon name="sparkle" size={12} />
          <span><b className="font-medium text-violet-300">Demo draft</b> - review and edit before sending. {draftNote}</span>
        </div>
      )}
      <ErrorLine error={error} />
    </div>
  );
}
