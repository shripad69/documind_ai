import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import MarkdownRenderer from './MarkdownRenderer';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test('renders numbered citation pills and binds them to the matching citation ids', () => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  const onCitation = jest.fn();
  const references = [
    { citation_id: 'chunk_1', citation_number: 1, document_id: 'same-pdf', file_name: 'Project Boreas.pdf' },
    { citation_id: 'chunk_2', citation_number: 2, document_id: 'same-pdf', file_name: 'Project Boreas.pdf' },
  ];

  act(() => root.render(
    <MarkdownRenderer
      content="The mission lasted 48 days [chunk_1]. The team processed 120 liters [chunk_2]."
      sourceReferences={references}
      onCitation={onCitation}
    />
  ));

  const pills = [...container.querySelectorAll('.citation-pill')];
  expect(pills.map(pill => pill.textContent)).toEqual(['[1]', '[2]']);
  act(() => pills[1].dispatchEvent(new MouseEvent('click', { bubbles: true })));
  expect(onCitation).toHaveBeenCalledWith(references[1], 1);

  act(() => root.unmount());
  container.remove();
});

