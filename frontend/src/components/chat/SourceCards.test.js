import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import SourceCards from './SourceCards';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test('renders every cited chunk as a separate card, including same-document citations', () => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  const references = [
    {
      citation_id: 'chunk_1', citation_number: 1, document_id: 'same-pdf', chunk_id: 'page-one',
      file_name: 'Project Boreas.pdf', page_number: 1, snippet: 'The mission lasted 48 days.',
      full_text: 'The mission\nlasted 48 days.', highlight_text: 'The mission lasted 48 days.',
    },
    {
      citation_id: 'chunk_2', citation_number: 2, document_id: 'same-pdf', chunk_id: 'page-three',
      file_name: 'Project Boreas.pdf', page_number: 3, snippet: 'The team collected 120 liters of brine.',
      full_text: 'The team collected 120 liters of brine.', highlight_text: 'The team collected 120 liters of brine.',
    },
  ];
  function Harness() {
    const [selected, setSelected] = React.useState(null);
    return <SourceCards
      references={references}
      selected={selected}
      onInspect={(source, index) => setSelected({ source, index })}
      onDismiss={() => setSelected(null)}
    />;
  }

  act(() => root.render(<Harness />));

  expect(container.querySelectorAll('.source-card')).toHaveLength(2);
  expect(container.querySelector('.source-grid').textContent).toContain('#1');
  expect(container.querySelector('.source-grid').textContent).toContain('#2');
  expect(container.querySelector('.source-grid').textContent).toContain('48 days');
  expect(container.querySelector('.source-grid').textContent).toContain('120 liters');

  act(() => container.querySelector('.source-card').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  expect(container.querySelector('.source-full-text mark').textContent).toBe('The mission\nlasted 48 days.');

  act(() => root.unmount());
  container.remove();
});

