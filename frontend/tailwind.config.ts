import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Primary surfaces
        surface: '#fff7fa',
        'surface-dim': '#e3d6df',
        'surface-bright': '#fff7fa',
        'surface-container-lowest': '#ffffff',
        'surface-container-low': '#fdf0f8',
        'surface-container': '#f8eaf3',
        'surface-container-high': '#f2e5ed',
        'surface-container-highest': '#ecdfe7',
        'on-surface': '#201a1f',
        'on-surface-variant': '#48473f',
        'inverse-surface': '#362e34',
        'inverse-on-surface': '#faedf5',
        outline: '#79776e',
        'outline-variant': '#c9c7bc',
        'surface-tint': '#5f5f50',

        // Primary
        primary: '#313225',
        'on-primary': '#ffffff',
        'primary-container': '#48483a',
        'on-primary-container': '#b8b7a5',
        'inverse-primary': '#c9c7b5',
        'primary-fixed': '#e5e3d0',
        'primary-fixed-dim': '#c9c7b5',
        'on-primary-fixed': '#1c1c11',
        'on-primary-fixed-variant': '#48483a',

        // Secondary
        secondary: '#6a5966',
        'on-secondary': '#ffffff',
        'secondary-container': '#f2dcec',
        'on-secondary-container': '#705f6c',
        'secondary-fixed': '#f2dcec',
        'secondary-fixed-dim': '#d6c1cf',
        'on-secondary-fixed': '#241822',
        'on-secondary-fixed-variant': '#51424e',

        // Tertiary
        tertiary: '#2e3131',
        'on-tertiary': '#ffffff',
        'tertiary-container': '#444847',
        'on-tertiary-container': '#b4b6b5',
        'tertiary-fixed': '#e1e3e2',
        'tertiary-fixed-dim': '#c4c7c6',
        'on-tertiary-fixed': '#191c1c',
        'on-tertiary-fixed-variant': '#444747',

        // Error
        error: '#ba1a1a',
        'on-error': '#ffffff',
        'error-container': '#ffdad6',
        'on-error-container': '#93000a',

        // Background
        background: '#fff7fa',
        'on-background': '#201a1f',
        'surface-variant': '#ecdfe7',
      },
      fontFamily: {
        serif: ['EB Garamond', 'serif'],
        sans: ['Metropolis', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'display-lg': ['48px', { lineHeight: '56px', fontWeight: '500', letterSpacing: '-0.01em' }],
        'display-lg-mobile': ['36px', { lineHeight: '42px', fontWeight: '500' }],
        'headline-md': ['32px', { lineHeight: '40px', fontWeight: '500' }],
        'headline-sm': ['24px', { lineHeight: '32px', fontWeight: '600' }],
        'body-lg': ['18px', { lineHeight: '28px', fontWeight: '400' }],
        'body-md': ['16px', { lineHeight: '24px', fontWeight: '400' }],
        'label-md': ['14px', { lineHeight: '20px', fontWeight: '600', letterSpacing: '0.02em' }],
        'label-sm': ['12px', { lineHeight: '16px', fontWeight: '700', letterSpacing: '0.05em' }],
      },
      borderRadius: {
        sm: '0.25rem',
        md: '0.75rem',
        lg: '1rem',
        xl: '1.5rem',
        full: '9999px',
      },
      spacing: {
        'gutter': '24px',
        'stack-sm': '8px',
        'stack-md': '16px',
        'stack-lg': '32px',
        'container-padding': '40px',
      },
      boxShadow: {
        'elevation-2': '0px 4px 20px rgba(44, 37, 43, 0.04)',
        'elevation-1': '0px 2px 8px rgba(44, 37, 43, 0.02)',
      },
    },
  },
  plugins: [],
} satisfies Config
