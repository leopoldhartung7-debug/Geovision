import type React from "react";
import { useCallback, useRef, useState } from "react";

interface Props {
  busy: boolean;
  onImages: (files: File[]) => void;
  onVideo: (file: File) => void;
}

const IMG = /\.(jpe?g|png|webp|heic|heif)$/i;
const VID = /\.(mp4|mov)$/i;

export default function UploadPanel({ busy, onImages, onVideo }: Props) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const dispatch = useCallback((files: File[]) => {
    const images = files.filter((f) => IMG.test(f.name) || f.type.startsWith("image/"));
    const videos = files.filter((f) => VID.test(f.name) || f.type.startsWith("video/"));
    if (videos.length) onVideo(videos[0]);
    if (images.length) onImages(images);
  }, [onImages, onVideo]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    dispatch(Array.from(e.dataTransfer.files));
  }, [dispatch]);

  return (
    <div className="card">
      <h2 className="font-bold mb-3">Upload</h2>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition
          ${drag ? "border-accent bg-panel2" : "border-edge"}`}
      >
        <div className="text-4xl mb-2">📍</div>
        <div className="font-semibold">Bilder oder Video hierher ziehen</div>
        <div className="text-muted text-sm mt-1">
          JPG · PNG · WEBP · HEIC · MP4 · MOV — Einzeln, Mehrfach oder Batch
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/*,video/mp4,video/quicktime,.heic,.heif"
          className="hidden"
          onChange={(e) => { if (e.target.files) dispatch(Array.from(e.target.files)); e.currentTarget.value = ""; }}
        />
      </div>
      {busy && <div className="text-accent text-sm mt-3 animate-pulse">Analysiere … (Modell lädt beim ersten Mal)</div>}
    </div>
  );
}
