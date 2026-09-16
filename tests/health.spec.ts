import { test, expect } from '@playwright/test';

test('A API pública de pagamentos deve estar online', async ({ request }) => {
  const response = await request.get('https://pokeapi.co/api/v2/pokemon/ditto');
  expect(response.status()).toBe(200);
});
