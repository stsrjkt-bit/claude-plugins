/**
 * GD（グループディスカッション）問題生成器 型定義
 */

export interface GDTheme {
  id: string;
  name: string;
  emoji: string;
  categoryId: string;
  year: number;
}

export interface KnowledgeCard {
  id: string;
  themeId: string;
  front: string;
  back: string;
  cardType: "daily_impact" | "number" | "product" | "comparison";
}

export interface OpinionProblem {
  id: string;
  themeId: string;
  question: string;
  choices: string[];
  modelAnswers: Record<
    string,
    {
      reason: string;
      example: string;
      keyPhrase: string;
      counterArguments: Array<{
        attack: string;
        defense: string;
      }>;
    }
  >;
}

export interface AxisProblem {
  id: string;
  themeId: string;
  opinions: Array<{
    speaker: string;
    content: string;
    tag: string;
  }>;
  modelAxes: Array<{
    axisName: string;
    group1: string[];
    group2: string[];
  }>;
}
