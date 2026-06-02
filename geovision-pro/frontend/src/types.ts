export interface GpsInfo {
  has_gps: boolean;
  lat?: number | null;
  lon?: number | null;
  altitude?: number | null;
  timestamp?: string | null;
  camera?: string | null;
  address?: string | null;
}

export interface SignalScore { label: string; score: number; }
export interface SignalGroup { name: string; top: SignalScore[]; weight: number; }

export interface LocationCandidate {
  rank: number;
  label: string;
  confidence: number;
  lat?: number | null;
  lon?: number | null;
  reasoning: string;
}

export interface Hierarchy {
  continent?: string | null;
  country?: string | null;
  region?: string | null;
  city?: string | null;
  district?: string | null;
  note: string;
}

export interface ReferenceMatch {
  name: string;
  similarity: number;
  lat?: number | null;
  lon?: number | null;
}

export interface AnalysisResult {
  id?: number;
  created_at?: string;
  kind: string;
  source_name: string;
  gps: GpsInfo;
  location_source: "exif" | "ocr" | "geoclip" | "inference";
  hierarchy: Hierarchy;
  candidates: LocationCandidate[];
  signals: SignalGroup[];
  ocr_text: string;
  reference_matches: ReferenceMatch[];
  uncertainty: string;
  model_used: string;
}

export interface JobListItem {
  id: number;
  created_at: string;
  kind: string;
  source_name: string;
  best_label?: string | null;
  best_confidence?: number | null;
  location_source: string;
}
