import assert from 'node:assert/strict';
import test from 'node:test';

import { prodIdentityError } from '../src/data/prod-identity.mjs';

test('sin SITE_BUILD=prod no exige identidad', () => {
  assert.equal(prodIdentityError({}), '');
  assert.equal(prodIdentityError({ SITE_BUILD: 'demo' }), '');
  assert.equal(prodIdentityError({ AGENCY_NAME: '', AGENCY_EMAIL: '' }), '');
});

test('SITE_BUILD=prod sin AGENCY_NAME o AGENCY_EMAIL nombra la variable', () => {
  const both = prodIdentityError({ SITE_BUILD: 'prod' });
  assert.match(both, /AGENCY_NAME/);
  assert.match(both, /AGENCY_EMAIL/);
  assert.match(both, /Build de producción del sitio/);

  const email = prodIdentityError({ SITE_BUILD: 'prod', AGENCY_NAME: 'Norte' });
  assert.match(email, /AGENCY_EMAIL/);
  assert.doesNotMatch(email, /AGENCY_NAME/);

  const name = prodIdentityError({ SITE_BUILD: 'prod', PUBLIC_AGENCY_EMAIL: 'a@b.cl' });
  assert.match(name, /AGENCY_NAME/);
  assert.doesNotMatch(name, /AGENCY_EMAIL/);

  assert.equal(
    prodIdentityError({
      SITE_BUILD: 'prod',
      PUBLIC_AGENCY_NAME: 'Norte',
      AGENCY_EMAIL: 'a@b.cl',
    }),
    '',
  );
});
