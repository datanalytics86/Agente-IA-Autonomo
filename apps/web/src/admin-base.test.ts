import { createMemoryHistory, createRouter } from '@tanstack/react-router'
import { describe, expect, it } from 'vitest'
import { ADMIN_BASEPATH } from './admin-base'
import { routeTree } from './routeTree.gen'

describe('base del dashboard', () => {
  it('la ruta de leads es /admin/leads', async () => {
    const history = createMemoryHistory({
      initialEntries: [`${ADMIN_BASEPATH}/leads`],
    })
    const router = createRouter({
      routeTree,
      history,
      basepath: ADMIN_BASEPATH,
    })
    await router.load()
    expect(router.state.location.pathname).toBe('/leads')
    expect(router.state.location.publicHref).toBe('/admin/leads')
  })
})
