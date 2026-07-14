import React from 'react';
import { initials } from '../../lib/format.js';

const GRADIENTS = {
  participant: 'linear-gradient(135deg,#1D4ED8,#3B82F6)',
  plan_sponsor: 'linear-gradient(135deg,#7C3AED,#818CF8)',
  plan_trustee: 'linear-gradient(135deg,#7C3AED,#818CF8)',
  investment_advisor: 'linear-gradient(135deg,#059669,#10B981)',
};

export default function Avatar({ name, principalType, size = 34 }) {
  const background = GRADIENTS[principalType] || GRADIENTS.participant;
  return (
    <div
      className="rounded-full flex items-center justify-center text-white font-semibold flex-shrink-0"
      style={{ width: size, height: size, background, fontSize: size * 0.34 }}
    >
      {initials(name)}
    </div>
  );
}
