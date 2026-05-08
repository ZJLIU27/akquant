/** Binance-inspired design tokens. */

export const colors = {
  yellow: '#F0B90B',
  gold: '#FFD000',
  lightGold: '#F8D12F',
  activeYellow: '#D0980B',
  focusBlue: '#1EAEDB',

  white: '#FFFFFF',
  snow: '#F5F5F5',
  dark: '#222126',
  darkCard: '#2B2F36',
  ink: '#1E2026',

  primaryText: '#1E2026',
  secondaryText: '#32313A',
  slate: '#848E9C',
  steel: '#686A6C',
  muted: '#777E90',

  green: '#0ECB81',
  red: '#F6465D',

  borderLight: '#E6E8EA',
  borderGold: '#FFD000',
} as const;

export const spacing = {
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  7: '32px',
  8: '48px',
} as const;

export const radius = {
  sm: '6px',
  md: '8px',
  lg: '12px',
  pill: '50px',
} as const;

export const shadow = {
  subtle: 'rgba(32, 32, 37, 0.05) 0px 3px 5px 0px',
  medium: 'rgba(8, 8, 8, 0.05) 0px 3px 5px 5px',
};
