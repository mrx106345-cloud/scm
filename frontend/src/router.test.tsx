import { afterEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, Link, NavLink, Route, Routes, useParams } from 'react-router-dom';

function Home() {
  return (
    <div>
      <h1>Home</h1>
      <Link to="/suppliers/SUP-9">Go supplier</Link>
    </div>
  );
}

function SupplierProbe() {
  const { id } = useParams<{ id: string }>();
  return <h1>Supplier {id}</h1>;
}

function renderApp() {
  return render(
    <BrowserRouter>
      <nav>
        <NavLink to="/" end>
          home-link
        </NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/suppliers/:id" element={<SupplierProbe />} />
      </Routes>
    </BrowserRouter>,
  );
}

describe('react-router v7 (app API surface)', () => {
  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('renders the matching route', () => {
    renderApp();
    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument();
  });

  it('extracts path params with useParams', () => {
    window.history.pushState({}, '', '/suppliers/SUP-9');
    renderApp();
    expect(screen.getByRole('heading', { name: 'Supplier SUP-9' })).toBeInTheDocument();
  });

  it('navigates on Link click', async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('link', { name: 'Go supplier' }));
    expect(await screen.findByRole('heading', { name: 'Supplier SUP-9' })).toBeInTheDocument();
  });

  it('marks the active NavLink', () => {
    renderApp();
    const link = screen.getByRole('link', { name: 'home-link' });
    expect(link).toHaveClass('active');
  });
});
