import ts from 'typescript-eslint';
import hooks from 'eslint-plugin-react-hooks';
import a11y from 'eslint-plugin-jsx-a11y';
export default ts.config({ignores:['src/api/generated.ts']},...ts.configs.recommended,{files:['src/**/*.{ts,tsx}'],plugins:{'react-hooks':hooks,'jsx-a11y':a11y},rules:{...hooks.configs.recommended.rules,...a11y.configs.recommended.rules,'@typescript-eslint/no-unused-vars':['error',{argsIgnorePattern:'^_'}]}});
