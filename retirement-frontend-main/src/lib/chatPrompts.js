// Suggested prompts shown in the chat composer, and intent classification
// used to pick an icon for each prompt chip.

export const SUGGESTED_PROMPTS = [
  'How much can I borrow?',
  'What is my vesting percentage?',
  'I want a loan of $10,000 for 5 years',
  'Change my deferral to 8%',
  'Reallocate to 60% COF-SP500 and 40% COF-LIFEPATH-2040',
  'I need a hardship withdrawal of $5,000 for medical expenses',
];

export function classifyIntent(rawText) {
  const text = rawText.toLowerCase();
  if (/how much (can|could) i borrow|loan headroom|max(imum)? (i can )?loan/.test(text)) return 'loan_inquiry';
  if (/\bloan\b|\bborrow\b/.test(text)) return 'loan_initiation';
  if (/hardship/.test(text)) return 'hardship_distribution';
  if (/deferral|contribution rate|contribute/.test(text) && /%/.test(text)) return 'deferral_change';
  if (/reallocat|rebalance|split .*%|move (everything|.* to)/.test(text)) return 'investment_reallocation';
  if (/beneficiary/.test(text)) return 'beneficiary_update';
  if (/address/.test(text)) return 'address_update';
  if (/vest/.test(text)) return 'vesting_inquiry';
  if (/balance|ytd|deferral rate|employment|years of service/.test(text)) return 'account_inquiry';
  return 'general_inquiry';
}
