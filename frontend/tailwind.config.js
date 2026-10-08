/** @type {import('tailwindcss').Config} */
// 语义色全部映射到 CSS 变量 --th-*（由 ThemeProvider 按所选主题写入），
// 类名（bg-brand-500 / text-muted 等）不用改，换主题自动变色。
const th = (v) => `var(--th-${v})`;
const mix = (color, pct, base) => `color-mix(in srgb, ${color} ${pct}%, ${base})`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        cream: th('bg'),
        brand: {
          50: mix(th('pri'), 6, th('card')),
          100: mix(th('pri'), 13, th('card')),
          200: mix(th('pri'), 26, th('card')),
          300: mix(th('pri'), 42, th('card')),
          400: mix(th('pri'), 66, th('card')),
          500: th('pri'),
          600: th('prid'),
          700: mix(th('prid'), 82, 'black'),
          DEFAULT: th('pri'),
        },
        sage: {
          100: mix(th('acc'), 16, th('card')),
          700: mix(th('acc'), 72, 'black'),
          DEFAULT: th('acc'),
        },
        ink: th('txt'),
        muted: th('mut'),
        clay: mix(th('mut'), 62, th('bg')),
        sand: th('line'),
      },
      boxShadow: {
        soft: '0 8px 28px rgba(122, 100, 84, 0.07)',
        lift: '0 14px 38px rgba(122, 100, 84, 0.10)',
      },
    },
  },
  plugins: [],
}
