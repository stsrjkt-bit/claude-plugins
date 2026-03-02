// CardData TypeScript Type Definitions
// Source: Section-Maker types.ts + Refainer types.ts (unified)

export interface IdLabel {
  id: string;
  label: string;
}

export interface IdText {
  id: string;
  text: string;
}

export interface VoiceData {
  parent: IdText;
  child: IdText;
}

export interface SolutionSummary {
  head: IdText;
  body: IdText;
}

export interface QuickAnswer {
  id: string;
  label: string;
  text: string;
}

export interface Guide {
  title: IdText;
  content: IdText;
}

export interface FaqItem {
  q: IdText;
  a: IdText;
}

export interface RecommendPoint {
  id: string;
  text: string;
}

export interface LinkUrl {
  id: string;
  url: string;
}

export interface Actions {
  guide: Guide;
  faq: FaqItem[];
  recommendPoints: RecommendPoint[];
  linkUrl?: LinkUrl;
  linkLabel?: IdText;
}

export interface DisplayPeriod {
  start: string; // "1" to "12"
  end: string;   // "1" to "12"
}

export interface GradeTag {
  id: string;
  label: string;
  displayPeriod?: { start: number; end: number }; // 省略時=カードの displayPeriod に従う
}

export interface CardData {
  id: string;
  category: string;
  displayPeriod: DisplayPeriod;
  gradeTags: GradeTag[];
  target: IdLabel;
  tags: IdLabel[];
  title: IdText;
  voice: VoiceData;
  solution_summary: SolutionSummary;
  quickAnswers: QuickAnswer[];
  actions: Actions;
}

// --- Research Types (Section-Maker) ---

export type GradeCategory = 'elementary' | 'middle' | 'high';

export interface ResearchParams {
  startMonth: string;
  endMonth: string;
  grade: GradeCategory;
  goal: string;
  memo: string;
}

export interface ResearchResult {
  text: string;
  sources: { title: string; uri: string }[];
}

export interface TradeAreaResult {
  text: string;
  places: { title: string; uri: string }[];
}

// --- Refainer Types ---

export interface StrengthMapping {
  gap: string;
  strength: string;
}

export interface CompetitorResearchResult {
  parentDissatisfactions: string[];
  studentDissatisfactions: string[];
  operationalGaps: string[];
  triggers: string[];
  strengthMapping: StrengthMapping[];
}

export interface Variation {
  label: string;
  description: string;
  displayPoints: string[];
}
