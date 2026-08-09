import { render, screen } from '@testing-library/react'
import App from './App'

describe('frontend baseline shell', () => {
  it('renders the login screen when unauthenticated', () => {
    render(<App />)
    expect(
      screen.getByRole('heading', { name: /sign in/i }),
    ).toBeInTheDocument()
  })
})
