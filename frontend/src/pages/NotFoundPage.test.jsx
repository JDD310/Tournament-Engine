import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '../test/helpers.jsx'

afterEach(() => vi.unstubAllGlobals())

describe('NotFoundPage', () => {
  it.each(['/foo', '/t', '/t/abc123/manage/extra', '/tournaments/abc123'])(
    'is shown for the unknown path %s, without calling the API',
    (path) => {
      const fetchMock = vi.fn()
      vi.stubGlobal('fetch', fetchMock)
      renderAt(path)

      expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Go to the home page' })).toHaveAttribute('href', '/')
      expect(fetchMock).not.toHaveBeenCalled()
    },
  )
})
