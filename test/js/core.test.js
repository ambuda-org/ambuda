import * as core from '@/core.ts';

window.Sanscript = {
  t: jest.fn((s, from, to) => `${s}:${to}`),
}


test('forEachTextNode transforms only Sanskrit text', () => {
  const $div = document.createElement('div');
  $div.innerHTML = `
  <div>bhASAH
    <p lang="sa">saMskRtam</p>
    <p lang="en">English</p>
    <p lang="fr">Francais</p>
  </div>
  `;
  core.forEachTextNode($div, (s) => s.toUpperCase());
  expect($div.innerHTML).toBe(`
  <div>BHASAH
    <p lang="sa">SAMSKRTAM</p>
    <p lang="en">English</p>
    <p lang="fr">Francais</p>
  </div>
  `);
});

test('transliterateElement transliterates Sanskrit fields', () => {
  const $div = document.createElement('div');
  $div.innerHTML = `
  <div>bhASAH
    <p lang="sa">saMskRtam</p>
    <p lang="en">English</p>
    <p lang="fr">Francais</p>
  </div>
  `;

  core.transliterateElement($div, 'hk', 'devanagari')
  $div.innerHTML = `
  <div>bhASAH
    <p lang="sa">saMskRtam:devanagari</p>
    <p lang="en">English</p>
    <p lang="fr">Francais</p>
  </div>
  `;
});
