/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // 暖米白底
        cream: '#FAF6F1',
        // 豆沙粉 / 雾玫红（主色）
        brand: {
          50: '#FBF4F5',
          100: '#F6E3E6',
          200: '#EAC2C9',
          300: '#DB9FAB',
          400: '#C97E8C',
          500: '#B76E79',
          600: '#A25964',
          700: '#854750',
        },
        // 鼠尾草绿（辅助色）
        sage: {
          50: '#F4F7F1',
          100: '#E5EDE0',
          200: '#CCDBC0',
          300: '#B0C6A0',
          400: '#9CAF88',
          500: '#8A9D75',
          600: '#72825F',
          700: '#5D6A4E',
        },
        // 暖深灰（正文）/ 暖灰（次要小字，≥4.5:1）/ 浅暖灰（装饰大字）
        ink: '#4A4239',
        muted: '#776A5D',
        clay: '#9A8F84',
        // 暖沙色（细分割线 / 浅底）
        sand: '#EDE5D8',
      },
      boxShadow: {
        soft: '0 8px 28px rgba(122, 100, 84, 0.07)',
        lift: '0 14px 38px rgba(122, 100, 84, 0.10)',
      },
    },
  },
  plugins: [],
}
