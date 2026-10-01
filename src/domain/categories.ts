export const CATEGORIES = [
    'alimentacao',
    'transporte',
    'moradia',
    'saude',
    'lazer',
    'educacao',
    'outros',
] as const;

export type Category = (typeof CATEGORIES)[number];
