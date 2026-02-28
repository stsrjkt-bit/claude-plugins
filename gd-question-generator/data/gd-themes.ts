/**
 * 滋賀県立大学 工学部 材料化学科 後期GD試験 予想問題データ
 *
 * 高校化学の教科書単元をベースに、過去問の出題パターン（2024-2025で収束）に
 * 忠実な温度感でGDテーマを網羅的に定義する。
 */

// ---------------------------------------------------------------------------
// 型定義
// ---------------------------------------------------------------------------

export const QUESTION_PATTERN_IDS = [
  "pattern1", // 枯渇型（2025年型）
  "pattern2", // 二者択一型（2024年型）
  "pattern3", // 三者択一型
  "pattern4", // 選択＋将来展望型
  "pattern5", // 是非判断型（2023年型）
] as const;
export type QuestionPattern = (typeof QUESTION_PATTERN_IDS)[number];

export const CATEGORY_IDS = [
  "element", // A 元素・資源
  "energy", // B エネルギー・電池
  "environment", // C 環境・リサイクル
  "methodology", // D 化学の学び方・方法論
  "medical", // E 医療・生命
  "food", // F 食・農業・水
  "industry", // G 産業・安全
  "material", // H 材料・素材
] as const;
export type CategoryId = (typeof CATEGORY_IDS)[number];

export interface GdTheme {
  /** テーマID（カテゴリ文字＋番号） */
  id: string;
  /** テーマ名（短縮形） */
  name: string;
  /** 表示用絵文字 */
  emoji: string;
  /** カテゴリID */
  categoryId: CategoryId;
  /** 予想出題年度 */
  year: number;
  /** 高校化学の対応単元 */
  textbookUnit: string;
  /** 問いかけパターン */
  questionPattern: QuestionPattern;
  /** 問題文 */
  question: string;
  /** 選択肢 */
  choices: string[];
  /** 出題済みフラグ */
  isAsked?: boolean;
}

export interface Category {
  id: CategoryId;
  label: string;
  color: string;
  sourceUnit: string;
}

export interface PastQuestion {
  year: number;
  question: string;
  evaluation: "good" | "bad";
  note: string;
}

export interface QuestionPatternDef {
  id: QuestionPattern;
  name: string;
  template: string;
  affinity: string;
}

// ---------------------------------------------------------------------------
// 過去問データ
// ---------------------------------------------------------------------------

export const PAST_QUESTIONS: PastQuestion[] = [
  {
    year: 2025,
    question:
      "Li, Ca, Si, Cu のいずれか一つが地球から枯渇したら、生活にどのような支障が生じるか。元素を一つ選択し、具体例を挙げて説明せよ。",
    evaluation: "good",
    note: "教科書の元素 × 「なくなったら？」→ 一番うまくいった",
  },
  {
    year: 2024,
    question:
      '化学関連の仕事に就くとして、大学で「化学」以外に学ぶ科目として「数学」と「物理」のどちらがより重要か。',
    evaluation: "good",
    note: "化学の教科書知識だけで語れる → まともな議論に",
  },
  {
    year: 2023,
    question:
      "空飛ぶクルマが実用化され始めている。日常的に使用することを日本で認めてもいいか。",
    evaluation: "bad",
    note: "未来技術だが法律の話に。化学関係薄い",
  },
  {
    year: 2022,
    question:
      "LED信号機への切替で消費電力が減った。同じ電気代で信号機を増やすか、LED化で電気代を安くするか。",
    evaluation: "bad",
    note: "急に化学寄りに。受験生に専門知識なく議論低調",
  },
  {
    year: 2021,
    question:
      "翻訳ソフト・通訳機器の発達で外国語スキルの意味が薄れている。英語教育を継続すべきか。",
    evaluation: "bad",
    note: "化学関係なし。ぼんやりした議論に",
  },
];

// ---------------------------------------------------------------------------
// カテゴリ定義
// ---------------------------------------------------------------------------

export const CATEGORIES: Category[] = [
  {
    id: "element",
    label: "A 元素・資源",
    color: "#EF4444",
    sourceUnit: "周期表、典型元素、遷移元素",
  },
  {
    id: "energy",
    label: "B エネルギー・電池",
    color: "#F59E0B",
    sourceUnit: "酸化還元、電池、電気分解、熱化学",
  },
  {
    id: "environment",
    label: "C 環境・リサイクル",
    color: "#10B981",
    sourceUnit: "高分子、有機化学、気体の性質",
  },
  {
    id: "methodology",
    label: "D 化学の学び方・方法論",
    color: "#6366F1",
    sourceUnit: "化学全般の学習姿勢",
  },
  {
    id: "medical",
    label: "E 医療・生命",
    color: "#EC4899",
    sourceUnit: "有機化学、タンパク質、糖類",
  },
  {
    id: "food",
    label: "F 食・農業・水",
    color: "#84CC16",
    sourceUnit: "窒素の化合物、リン、アンモニア合成",
  },
  {
    id: "industry",
    label: "G 産業・安全",
    color: "#8B5CF6",
    sourceUnit: "工業的製法、化学反応の速さ、触媒",
  },
  {
    id: "material",
    label: "H 材料・素材",
    color: "#06B6D4",
    sourceUnit: "金属結合、共有結合結晶、高分子、セラミクス",
  },
];

// ---------------------------------------------------------------------------
// 問いかけパターン定義
// ---------------------------------------------------------------------------

export const QUESTION_PATTERNS: QuestionPatternDef[] = [
  {
    id: "pattern1",
    name: "枯渇型（2025年型）",
    template:
      "A, B, C, D のいずれか一つが〇〇したら、△△にどのような影響が生じるか。一つ選び、具体例を挙げて説明せよ",
    affinity: "元素・資源テーマと相性が良い",
  },
  {
    id: "pattern2",
    name: "二者択一型（2024年型）",
    template:
      "〇〇と△△のどちらがより□□か。一方を選び、理由を述べよ",
    affinity: "方法論比較、技術比較テーマと相性が良い",
  },
  {
    id: "pattern3",
    name: "三者択一型",
    template:
      "A, B, C のうち、最も□□なのはどれか。一つ選び、具体的な根拠を挙げて論じよ",
    affinity: "プロセスの段階比較、複数要因比較テーマと相性が良い",
  },
  {
    id: "pattern4",
    name: "選択＋将来展望型",
    template:
      "A, B, C, D のいずれか一つを選び、〇〇の観点から今後どのような役割を果たしうるか。現在の用途と比較しながら具体的に論じよ",
    affinity: "元素・材料テーマの将来展望と相性が良い",
  },
  {
    id: "pattern5",
    name: "是非判断型（2023年型）",
    template:
      "〇〇は△△にとってプラスかマイナスか。自分の考えを述べよ",
    affinity:
      "技術の社会的影響テーマと相性が良い（ただしこの型は2024以降使われていない）",
  },
];

// ---------------------------------------------------------------------------
// GDテーマ一覧
// ---------------------------------------------------------------------------

export const GD_THEMES: GdTheme[] = [
  // =======================================================================
  // カテゴリA：元素・資源
  // =======================================================================
  {
    id: "a1",
    name: "Li/Ca/Si/Cu枯渇",
    emoji: "🪨",
    categoryId: "element",
    year: 2025,
    textbookUnit: "典型・遷移元素の性質",
    questionPattern: "pattern1",
    question:
      "Li, Ca, Si, Cu のいずれか一つが地球から枯渇したら、生活にどのような支障が生じるか。元素を一つ選択し、具体例を挙げて説明せよ。",
    choices: ["Li", "Ca", "Si", "Cu"],
    isAsked: true,
  },
  {
    id: "a2",
    name: "金属元素の将来",
    emoji: "⚙️",
    categoryId: "element",
    year: 2028,
    textbookUnit: "金属の性質、イオン化傾向",
    questionPattern: "pattern4",
    question:
      "Fe, Al, Ti, Mg のいずれか一つを選び、今後の社会でどのような新しい役割を果たしうるか。現在の用途と比較しながら具体的に論じよ。",
    choices: ["Fe", "Al", "Ti", "Mg"],
  },
  {
    id: "a3",
    name: "レアアースvsコモンメタル",
    emoji: "⚖️",
    categoryId: "element",
    year: 2029,
    textbookUnit: "遷移元素、周期表",
    questionPattern: "pattern2",
    question:
      "レアアース（希土類元素）とコモンメタル（鉄・アルミなど）のどちらの研究開発が、今後の社会にとってより重要か。一方を選び、理由を述べよ。",
    choices: ["レアアース", "コモンメタル"],
  },
  {
    id: "a4",
    name: "貴金属の価値",
    emoji: "✨",
    categoryId: "element",
    year: 2030,
    textbookUnit: "遷移元素、電気伝導性",
    questionPattern: "pattern5",
    question:
      "金(Au)・銀(Ag)・銅(Cu)などの貴金属は、工業材料としての価値と装飾品としての価値のどちらが今後より重要になるか。自分の考えを述べよ。",
    choices: ["工業材料としての価値", "装飾品としての価値"],
  },
  {
    id: "a5",
    name: "人体と元素",
    emoji: "🧬",
    categoryId: "element",
    year: 2031,
    textbookUnit: "アルカリ金属、アルカリ土類金属、電解質",
    questionPattern: "pattern3",
    question:
      "Na, K, Ca は人体の機能維持に不可欠な元素である。これらのうち、不足した場合に最も深刻な影響が出るのはどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["Na", "K", "Ca"],
  },

  // =======================================================================
  // カテゴリB：エネルギー・電池
  // =======================================================================
  {
    id: "b1",
    name: "水素エネルギーの課題",
    emoji: "💧",
    categoryId: "energy",
    year: 2026,
    textbookUnit: "水の電気分解、燃料電池",
    questionPattern: "pattern3",
    question:
      "水素エネルギーの普及において、製造・貯蔵・利用のうち、最も大きな課題はどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["製造", "貯蔵", "利用"],
  },
  {
    id: "b2",
    name: "次世代電池",
    emoji: "🔋",
    categoryId: "energy",
    year: 2027,
    textbookUnit: "ダニエル電池、鉛蓄電池、リチウムイオン電池",
    questionPattern: "pattern3",
    question:
      "リチウムイオン電池・全固体電池・ナトリウムイオン電池のうち、今後10年で最も社会に普及する電池はどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["リチウムイオン電池", "全固体電池", "ナトリウムイオン電池"],
  },
  {
    id: "b3",
    name: "再エネの主役",
    emoji: "☀️",
    categoryId: "energy",
    year: 2028,
    textbookUnit: "光エネルギー、電気化学",
    questionPattern: "pattern2",
    question:
      "再生可能エネルギーの主役として、太陽電池と燃料電池のどちらがより有望か。一方を選び、化学的な観点から理由を述べよ。",
    choices: ["太陽電池", "燃料電池"],
  },
  {
    id: "b4",
    name: "原子力の是非",
    emoji: "⚛️",
    categoryId: "energy",
    year: 2029,
    textbookUnit: "放射性同位体、核反応",
    questionPattern: "pattern5",
    question:
      "原子力発電は、日本のエネルギー問題の解決にとってプラスかマイナスか。化学的な観点を含めて自分の考えを述べよ。",
    choices: ["プラス", "マイナス"],
  },

  // =======================================================================
  // カテゴリC：環境・リサイクル
  // =======================================================================
  {
    id: "c1",
    name: "プラスチックごみ対策",
    emoji: "♻️",
    categoryId: "environment",
    year: 2027,
    textbookUnit: "高分子化合物、付加重合・縮合重合",
    questionPattern: "pattern2",
    question:
      "プラスチックごみの問題を解決するために、生分解性プラスチックへの置き換えとリサイクル技術の向上のどちらがより有効か。一方を選び、理由を述べよ。",
    choices: ["生分解性プラスチックへの置き換え", "リサイクル技術の向上"],
  },
  {
    id: "c2",
    name: "CO₂との向き合い方",
    emoji: "🌍",
    categoryId: "environment",
    year: 2026,
    textbookUnit: "気体の性質、化学平衡",
    questionPattern: "pattern2",
    question:
      "地球温暖化への対策として、CO₂の排出削減とCO₂の回収・再利用のどちらにより多くの投資をすべきか。一方を選び、理由を述べよ。",
    choices: ["CO₂の排出削減", "CO₂の回収・再利用"],
  },
  {
    id: "c3",
    name: "大気汚染対策",
    emoji: "🌫️",
    categoryId: "environment",
    year: 2030,
    textbookUnit: "酸・塩基、SO₂/NOₓ",
    questionPattern: "pattern3",
    question:
      "大気汚染対策として、排煙脱硫（SO₂除去）・排煙脱硝（NOₓ除去）・粒子状物質（PM）除去のうち、最も優先すべきはどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["排煙脱硫（SO₂除去）", "排煙脱硝（NOₓ除去）", "粒子状物質（PM）除去"],
  },
  {
    id: "c4",
    name: "水の浄化技術",
    emoji: "🚰",
    categoryId: "environment",
    year: 2031,
    textbookUnit: "コロイド、凝析、吸着",
    questionPattern: "pattern3",
    question:
      "安全な飲料水を確保するための化学技術として、塩素消毒・活性炭吸着・膜ろ過のうち、最も重要なのはどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["塩素消毒", "活性炭吸着", "膜ろ過"],
  },
  {
    id: "c5",
    name: "ゴミ処理の最適解",
    emoji: "🗑️",
    categoryId: "environment",
    year: 2032,
    textbookUnit: "燃焼反応、高分子化合物",
    questionPattern: "pattern3",
    question:
      "ゴミの処理方法として、焼却・埋め立て・リサイクルのうち、化学的に最も合理的なのはどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["焼却", "埋め立て", "リサイクル"],
  },

  // =======================================================================
  // カテゴリD：化学の学び方・方法論
  // =======================================================================
  {
    id: "d1",
    name: "数学vs物理",
    emoji: "📐",
    categoryId: "methodology",
    year: 2024,
    textbookUnit: "化学と他分野の関係",
    questionPattern: "pattern2",
    question:
      "化学関連の仕事に就くとして、大学で「化学」以外に学ぶ科目として「数学」と「物理」のどちらがより重要か。",
    choices: ["数学", "物理"],
    isAsked: true,
  },
  {
    id: "d2",
    name: "実験vsAI計算",
    emoji: "🤖",
    categoryId: "methodology",
    year: 2026,
    textbookUnit: "実験操作、データ処理",
    questionPattern: "pattern2",
    question:
      "化学の研究において、実験による検証とAI・コンピュータによる予測のどちらがより重要になると考えるか。一方を選び、理由を述べよ。",
    choices: ["実験による検証", "AI・コンピュータによる予測"],
  },
  {
    id: "d3",
    name: "基礎研究vs応用研究",
    emoji: "🔬",
    categoryId: "methodology",
    year: 2028,
    textbookUnit: "科学の方法論",
    questionPattern: "pattern2",
    question:
      "化学の発展のためには、基礎研究と応用研究のどちらにより多くの予算を配分すべきか。一方を選び、理由を述べよ。",
    choices: ["基礎研究", "応用研究"],
  },
  {
    id: "d4",
    name: "個人vsチーム",
    emoji: "👥",
    categoryId: "methodology",
    year: 2029,
    textbookUnit: "科学者の働き方",
    questionPattern: "pattern2",
    question:
      "化学の画期的な発見に、個人の天才的研究とチームによる組織的研究のどちらがより貢献すると思うか。一方を選び、具体例を挙げて論じよ。",
    choices: ["個人の天才的研究", "チームによる組織的研究"],
  },

  // =======================================================================
  // カテゴリE：医療・生命
  // =======================================================================
  {
    id: "e1",
    name: "天然物vs人工分子の創薬",
    emoji: "💊",
    categoryId: "medical",
    year: 2027,
    textbookUnit: "有機化合物の分類",
    questionPattern: "pattern2",
    question:
      "新しい医薬品を開発するにあたり、天然物（植物・微生物由来）から探すアプローチと、人工的に分子を設計するアプローチのどちらがより有望か。一方を選び、理由を述べよ。",
    choices: ["天然物から探すアプローチ", "人工的に分子を設計するアプローチ"],
  },
  {
    id: "e2",
    name: "消毒・殺菌の化学",
    emoji: "🧴",
    categoryId: "medical",
    year: 2030,
    textbookUnit: "酸化還元、ハロゲン",
    questionPattern: "pattern3",
    question:
      "感染症対策に用いる消毒技術として、塩素系消毒・アルコール消毒・紫外線殺菌のうち、最も重要なのはどれか。一つ選び、化学的な根拠を挙げて論じよ。",
    choices: ["塩素系消毒", "アルコール消毒", "紫外線殺菌"],
  },
  {
    id: "e3",
    name: "食品添加物の安全性",
    emoji: "🍽️",
    categoryId: "medical",
    year: 2031,
    textbookUnit: "有機化合物、化学反応",
    questionPattern: "pattern5",
    question:
      "食品添加物（保存料・着色料・甘味料など）の使用は、社会にとってプラスかマイナスか。化学の観点を含めて自分の考えを述べよ。",
    choices: ["プラス", "マイナス"],
  },

  // =======================================================================
  // カテゴリF：食・農業・水
  // =======================================================================
  {
    id: "f1",
    name: "農業と元素の不足",
    emoji: "🌾",
    categoryId: "food",
    year: 2027,
    textbookUnit: "ハーバー・ボッシュ法、肥料の三要素",
    questionPattern: "pattern3",
    question:
      "農業に不可欠な肥料の三要素 N（窒素）・P（リン）・K（カリウム）のうち、将来最も不足が深刻になる元素はどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["N（窒素）", "P（リン）", "K（カリウム）"],
  },
  {
    id: "f2",
    name: "農薬の功罪",
    emoji: "🧪",
    categoryId: "food",
    year: 2029,
    textbookUnit: "有機化合物、環境問題",
    questionPattern: "pattern5",
    question:
      "農薬の使用は、食料生産と環境保全を総合的に考えたとき、社会にとってプラスかマイナスか。化学の観点を含めて自分の考えを述べよ。",
    choices: ["プラス", "マイナス"],
  },
  {
    id: "f3",
    name: "食の安全を守る技術",
    emoji: "🔍",
    categoryId: "food",
    year: 2032,
    textbookUnit: "分析化学の基礎",
    questionPattern: "pattern3",
    question:
      "食の安全を守るための化学技術として、残留農薬検査・食品添加物分析・微生物検査のうち、最も重要なのはどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["残留農薬検査", "食品添加物分析", "微生物検査"],
  },

  // =======================================================================
  // カテゴリG：産業・安全
  // =======================================================================
  {
    id: "g1",
    name: "化学工場の安全",
    emoji: "🏭",
    categoryId: "industry",
    year: 2034,
    textbookUnit: "反応速度、発熱反応",
    questionPattern: "pattern3",
    question:
      "化学工場の事故を防ぐために、設備改善・人材教育・法規制のうち、最も重要なのはどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["設備改善", "人材教育", "法規制"],
  },
  {
    id: "g2",
    name: "触媒の重要性",
    emoji: "⚗️",
    categoryId: "industry",
    year: 2030,
    textbookUnit: "触媒、反応速度",
    questionPattern: "pattern5",
    question:
      "触媒の開発は、化学のあらゆる研究分野の中で最も重要な分野と言えるか。自分の考えを述べよ。",
    choices: ["最も重要と言える", "他にもっと重要な分野がある"],
  },
  {
    id: "g3",
    name: "脱石油は可能か",
    emoji: "🛢️",
    categoryId: "industry",
    year: 2028,
    textbookUnit: "石油の分留、有機化学工業",
    questionPattern: "pattern2",
    question:
      "化学工業の原料を石油から植物由来のバイオマスに転換することは現実的か、それとも石油を使い続けるべきか。一方を選び、理由を述べよ。",
    choices: ["バイオマスへの転換", "石油の継続使用"],
  },

  // =======================================================================
  // カテゴリH：材料・素材
  // =======================================================================
  {
    id: "h1",
    name: "21世紀の主役材料",
    emoji: "🧱",
    categoryId: "material",
    year: 2026,
    textbookUnit: "結合と物質の分類",
    questionPattern: "pattern3",
    question:
      "21世紀のものづくりにおいて、金属・樹脂（プラスチック）・セラミクスのうち、最も重要な役割を果たす材料はどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["金属", "樹脂（プラスチック）", "セラミクス"],
  },
  {
    id: "h2",
    name: "繊維の未来",
    emoji: "🧵",
    categoryId: "material",
    year: 2029,
    textbookUnit: "高分子化合物（天然・合成）",
    questionPattern: "pattern2",
    question:
      "衣料の未来として、天然繊維（綿・絹・毛）への回帰と合成繊維（ナイロン・ポリエステル）の進化のどちらがより望ましいか。一方を選び、理由を述べよ。",
    choices: ["天然繊維への回帰", "合成繊維の進化"],
  },
  {
    id: "h3",
    name: "セラミクスの貢献",
    emoji: "🏺",
    categoryId: "material",
    year: 2031,
    textbookUnit: "共有結合結晶、ケイ素化合物",
    questionPattern: "pattern3",
    question:
      "ガラス・セメント・陶磁器のうち、人類の生活に最も貢献しているセラミクスはどれか。一つ選び、具体的な根拠を挙げて論じよ。",
    choices: ["ガラス", "セメント", "陶磁器"],
  },
  {
    id: "h4",
    name: "合金の設計思想",
    emoji: "🔩",
    categoryId: "material",
    year: 2032,
    textbookUnit: "金属の性質、混合物",
    questionPattern: "pattern2",
    question:
      "金属を使う場面で、純金属のまま使うことと合金にして使うことのどちらがより合理的か。一方を選び、具体例を挙げて理由を述べよ。",
    choices: ["純金属のまま使う", "合金にして使う"],
  },
];
