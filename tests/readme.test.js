const fs = require('fs');
const path = require('path');

test('README contains demo instructions', () => {
  const readme = fs.readFileSync(path.join(__dirname, '..', 'README.md'), 'utf8');
  expect(readme).toMatch(/Run Demo/);
});
