import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { generateStudySet } from '../../api';
import StudyOverlay from './StudyOverlay';

jest.mock('../../api', () => ({
  __esModule: true,
  default: {},
  getErrorMessage: error => error?.message || 'Something went wrong.',
  generateStudySet: jest.fn(),
}));

window.IS_REACT_ACT_ENVIRONMENT = true;

const documents = [
  { id: 'doc-1', file_name: 'AI Foundations.pdf', status: 'indexed' },
  { id: 'doc-2', file_name: 'ML Survey.pdf', status: 'indexed' },
  { id: 'doc-3', file_name: 'Still Processing.pdf', status: 'processing' },
];

const reference = {
  citation_id: 'chunk_1',
  citation_number: 1,
  document_id: 'doc-1',
  file_name: 'AI Foundations.pdf',
  page_number: 4,
  snippet: 'Solar panels provide power to the rover.',
  full_text: 'Solar panels provide power to the rover during daylight hours.',
  highlight_text: 'Solar panels provide power',
};

const flashcardSet = {
  mode: 'flashcards',
  difficulty: 'medium',
  document_names: ['AI Foundations.pdf'],
  flashcards: [
    {
      id: 'flashcard-1',
      front: 'What powers the rover?',
      back: 'Solar panels provide power [chunk_1].',
      source_references: [reference],
    },
  ],
  questions: [],
};

const quizSet = {
  mode: 'quiz',
  difficulty: 'medium',
  document_names: ['AI Foundations.pdf'],
  flashcards: [],
  questions: [
    {
      id: 'question-1',
      question: 'Which power source is used by the rover?',
      options: ['Batteries', 'Wind turbine', 'Solar panels', 'Nuclear cell'],
      correct_index: 2,
      explanation: 'The passage states that solar panels provide power [chunk_1].',
      source_references: [reference],
    },
  ],
};

let roots = [];

function setup(props = {}) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  roots.push(root);
  act(() => root.render(
    <StudyOverlay
      open
      workspace={{ id: 'ws-1', title: 'Research Workspace' }}
      documents={documents}
      onClose={jest.fn()}
      {...props}
    />
  ));
  return container;
}

function click(element) {
  act(() => {
    element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
}

async function generate(container) {
  await act(async () => {
    container.querySelector('.study-generate-button')
      .dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await Promise.resolve();
    await Promise.resolve();
  });
}

afterEach(() => {
  roots.forEach(root => act(() => root.unmount()));
  roots = [];
  document.body.innerHTML = '';
  jest.clearAllMocks();
});

test('switches between flashcard and quiz modes', () => {
  const container = setup();
  const [flashcards, quiz] = container.querySelectorAll('.study-mode-option');

  expect(flashcards.getAttribute('aria-pressed')).toBe('true');
  expect(quiz.getAttribute('aria-pressed')).toBe('false');

  click(quiz);

  expect(quiz.getAttribute('aria-pressed')).toBe('true');
  expect(flashcards.getAttribute('aria-pressed')).toBe('false');
});

test('flips a flashcard on click and requests all indexed documents by default', async () => {
  generateStudySet.mockResolvedValue(flashcardSet);
  const container = setup();

  await generate(container);

  expect(generateStudySet).toHaveBeenCalledWith('ws-1', {
    mode: 'flashcards',
    documentIds: ['doc-1', 'doc-2'],
    count: 8,
    difficulty: 'medium',
  });

  const card = container.querySelector('.study-flashcard');
  expect(card.className).not.toContain('flipped');
  expect(container.querySelector('.study-card-front h3').textContent).toContain('What powers the rover?');

  click(card);
  expect(card.className).toContain('flipped');

  click(card);
  expect(card.className).not.toContain('flipped');
});

test('reveals quiz feedback, opens the [1] source inspector, and reviews missed questions', async () => {
  generateStudySet.mockResolvedValue(quizSet);
  const container = setup();

  const [, quiz] = container.querySelectorAll('.study-mode-option');
  click(quiz);
  await generate(container);

  expect(generateStudySet).toHaveBeenCalledWith('ws-1', {
    mode: 'quiz',
    documentIds: ['doc-1', 'doc-2'],
    count: 8,
    difficulty: 'medium',
  });

  const options = container.querySelectorAll('.study-option');
  expect(options).toHaveLength(4);
  expect(container.querySelector('.study-explanation')).toBeNull();

  click(options[0]);

  expect(container.querySelector('.study-option.incorrect')).not.toBeNull();
  expect(container.querySelector('.study-option.correct')).not.toBeNull();
  expect(container.querySelector('.study-explanation').textContent).toContain('solar panels provide power');
  expect(container.querySelector('.study-quiz-score').textContent).toContain('0 correct');

  const citationPill = container.querySelector('.study-explanation .citation-pill');
  expect(citationPill.textContent).toBe('[1]');

  click(citationPill);
  expect(container.querySelector('.source-full-text').textContent)
    .toContain('Solar panels provide power to the rover');

  click(container.querySelector('.source-dialog .icon-button'));
  expect(container.querySelector('.source-full-text')).toBeNull();

  click(container.querySelector('.study-quiz-actions .primary-button'));
  expect(container.querySelector('.study-quiz-summary')).not.toBeNull();
  expect(container.querySelector('.study-quiz-summary').textContent).toContain('0 / 1');

  click(container.querySelector('.study-summary-actions .secondary-button'));
  expect(container.querySelector('.study-quiz-head h3').textContent)
    .toContain('Which power source is used by the rover?');
});

test('closes the overlay when Escape is pressed', () => {
  const onClose = jest.fn();
  setup({ onClose });

  act(() => {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  });

  expect(onClose).toHaveBeenCalledTimes(1);
});
