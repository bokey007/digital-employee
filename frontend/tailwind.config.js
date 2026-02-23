/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                brand: {
                    50: '#e6fbf0',
                    100: '#b3f3d4',
                    200: '#80ebb8',
                    300: '#4de39c',
                    400: '#1adb80',
                    500: '#00E47C',  // BI accent green
                    600: '#00c76c',
                    700: '#00a85c',
                    800: '#08312A',  // BI dark green
                    900: '#062520',
                    950: '#041a16',
                },
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
            },
        },
    },
    plugins: [
        require('@tailwindcss/typography'),
    ],
}
