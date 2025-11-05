module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/test', '<rootDir>/lambda'],
  testMatch: ['**/*.spec.ts', '**/*.test.ts'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  collectCoverageFrom: [
    'src/**/*.ts',
    'lambda/**/*.ts',
    '!src/**/*.spec.ts',
    '!src/**/*.test.ts',
    '!lambda/**/*.spec.ts',
    '!lambda/**/*.test.ts',
    '!src/cmd/**'
  ]
};
