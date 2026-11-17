import React, { useEffect, useRef, useState } from 'react';
import { generateStudySet, getErrorMessage } from '../../api';
import { Icon } from '../ui/Icons';
import MarkdownRenderer from '../chat/MarkdownRenderer';
import SourceCards from '../chat/SourceCards';

const studyStages = [
  'Reading the selected document sections…',
  'Drafting study items across your sources…',
  'Verifying every claim against retrieved passages…',
  'Assembling your citation-backed study set…',
];

const COUNTS = [5, 8, 12];
const DIFFICULTIES = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
];

function optionLetter(index) {
  return String.fromCharCode(65 + index);
}

export default function StudyOverlay({ open, workspace, documents = [], onClose }) {
  const panelRef = useRef(null);
  const restoreFocusRef = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  const [mode, setMode] = useState('flashcards');
  const [count, setCount] = useState(8);
  const [difficulty, setDifficulty] = useState('medium');
  const [selectedDocs, setSelectedDocs] = useState(null);
  const [studySet, setStudySet] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [error, setError] = useState('');

  const [cardIndex, setCardIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [cardStatuses, setCardStatuses] = useState({});

  const [questionIndex, setQuestionIndex] = useState(0);
  const [selections, setSelections] = useState({});
  const [quizFinished, setQuizFinished] = useState(false);
  const [quizFilter, setQuizFilter] = useState(null);
  const [selectedSource, setSelectedSource] = useState(null);

  const indexedDocs = documents.filter(document => document.status === 'indexed');
  const selectedDocumentIds = selectedDocs ?? indexedDocs.map(document => document.id);

  const cards = studySet?.mode === 'flashcards' ? studySet.flashcards || [] : [];
  const baseQuestions = studySet?.mode === 'quiz' ? studySet.questions || [] : [];
  const quizQuestions = quizFilter
    ? baseQuestions.filter(question => quizFilter.includes(question.id))
    : baseQuestions;
  const currentCard = cards[cardIndex] || null;
  const currentQuestion = quizQuestions[questionIndex] || null;
  const currentSelection = currentQuestion ? selections[currentQuestion.id] : undefined;

  const answeredCount = quizQuestions.filter(
    question => selections[question.id] !== undefined
  ).length;
  const score = quizQuestions.filter(
    question => selections[question.id] === question.correct_index
  ).length;
  const missedIds = quizQuestions
    .filter(question => selections[question.id] !== question.correct_index)
    .map(question => question.id);
  const knownCount = cards.filter(card => cardStatuses[card.id] === 'known').length;
  const reviewCount = cards.filter(card => cardStatuses[card.id] === 'review').length;
  const quizProgress = quizQuestions.length
    ? Math.round((answeredCount / quizQuestions.length) * 100)
    : 0;
  const percentage = quizQuestions.length
    ? Math.round((score / quizQuestions.length) * 100)
    : 0;

  useEffect(() => {
    if (!open) return undefined;
    restoreFocusRef.current = document.activeElement;
    setMode('flashcards');
    setCount(8);
    setDifficulty('medium');
    setSelectedDocs(null);
    setStudySet(null);
    setLoading(false);
    setLoadingStage(0);
    setError('');
    setCardIndex(0);
    setFlipped(false);
    setCardStatuses({});
    setQuestionIndex(0);
    setSelections({});
    setQuizFinished(false);
    setQuizFilter(null);
    setSelectedSource(null);
    const frame = window.setTimeout(() => panelRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(frame);
      const previous = restoreFocusRef.current;
      if (previous && typeof previous.focus === 'function') previous.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!loading) return undefined;
    setLoadingStage(0);
    const timer = window.setInterval(
      () => setLoadingStage(value => Math.min(value + 1, studyStages.length - 1)),
      1700
    );
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    if (!open) return undefined;
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeRef.current?.();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = [...panelRef.current.querySelectorAll(
        'button:not(:disabled),input:not(:disabled),textarea:not(:disabled),[href],[tabindex="0"]'
      )].filter(element => element !== panelRef.current && element.getClientRects().length);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  function clearGenerated() {
    setStudySet(null);
    setError('');
    setSelectedSource(null);
    setCardIndex(0);
    setFlipped(false);
    setCardStatuses({});
    setQuestionIndex(0);
    setSelections({});
    setQuizFinished(false);
    setQuizFilter(null);
  }

  function changeMode(nextMode) {
    setMode(nextMode);
    clearGenerated();
  }

  function toggleDocument(documentId) {
    setSelectedDocs(current => {
      const list = current ?? indexedDocs.map(document => document.id);
      const exists = list.some(value => String(value) === String(documentId));
      return exists
        ? list.filter(value => String(value) !== String(documentId))
        : [...list, documentId];
    });
    clearGenerated();
  }

  function changeCount(nextCount) {
    setCount(nextCount);
    clearGenerated();
  }

  function changeDifficulty(nextDifficulty) {
    setDifficulty(nextDifficulty);
    clearGenerated();
  }

  async function handleGenerate() {
    if (!workspace || !selectedDocumentIds.length) {
      setError('Select at least one indexed document to generate a study set.');
      return;
    }
    setLoading(true);
    setLoadingStage(0);
    setError('');
    setSelectedSource(null);
    try {
      const payload = await generateStudySet(workspace.id, {
        mode,
        documentIds: selectedDocumentIds,
        count,
        difficulty,
      });
      const items = payload.mode === 'quiz' ? payload.questions : payload.flashcards;
      if (!items || !items.length) {
        throw new Error('The study set came back empty. Please regenerate.');
      }
      setStudySet(payload);
      setCardIndex(0);
      setFlipped(false);
      setCardStatuses({});
      setQuestionIndex(0);
      setSelections({});
      setQuizFinished(false);
      setQuizFilter(null);
      setSelectedSource(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleCitation(reference, index) {
    setSelectedSource({ source: reference, index });
  }

  function handleCardClick(event) {
    if (event.target.closest('button')) return;
    setFlipped(value => !value);
  }

  function handleCardKeyDown(event) {
    if (event.target !== event.currentTarget) return;
    if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault();
      setFlipped(value => !value);
    }
  }

  function moveCard(offset) {
    const next = Math.min(Math.max(cardIndex + offset, 0), cards.length - 1);
    setCardIndex(next);
    setFlipped(false);
    setSelectedSource(null);
  }

  function markCard(status) {
    if (!currentCard) return;
    setCardStatuses(current => ({ ...current, [currentCard.id]: status }));
  }

  function selectOption(index) {
    if (!currentQuestion || currentSelection !== undefined) return;
    setSelections(current => ({ ...current, [currentQuestion.id]: index }));
    setSelectedSource(null);
  }

  function goNextQuestion() {
    if (questionIndex < quizQuestions.length - 1) {
      setQuestionIndex(value => value + 1);
      setSelectedSource(null);
    } else {
      setQuizFinished(true);
    }
  }

  function restartQuiz(onlyMissed) {
    if (onlyMissed && !missedIds.length) return;
    setQuizFilter(onlyMissed ? missedIds : null);
    setQuestionIndex(0);
    setSelections({});
    setQuizFinished(false);
    setSelectedSource(null);
  }

  function optionClass(index) {
    if (currentSelection === undefined || !currentQuestion) return 'study-option';
    if (index === currentQuestion.correct_index) return 'study-option correct';
    if (index === currentSelection) return 'study-option incorrect';
    return 'study-option muted';
  }

  if (!open) return null;

  return (
    <div className="study-overlay" role="presentation">
      <section
        className="study-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="study-title"
        ref={panelRef}
        tabIndex={-1}
      >
        <header className="study-header">
          <div className="study-header-left">
            <span className="study-header-icon">
              <Icon name="Study" size={18} />
            </span>
            <div className="study-header-copy">
              <h2 id="study-title">Study Mode</h2>
              <span>{workspace?.title || 'Workspace'} · flashcards and quizzes</span>
            </div>
          </div>
          <div className="study-header-actions">
            <span className="study-source-count">
              {selectedDocumentIds.length} of {indexedDocs.length} sources
            </span>
            <button
              type="button"
              className="study-close-button"
              onClick={onClose}
              aria-label="Close Study Mode"
              title="Close Study Mode"
            >
              <Icon name="X" size={18} />
            </button>
          </div>
        </header>

        <div className="study-body">
          <aside className="study-config">
            <section className="study-config-group">
              <span className="study-config-label">Mode</span>
              <div className="study-mode-switch" role="group" aria-label="Study mode">
                <button
                  type="button"
                  className={`study-mode-option ${mode === 'flashcards' ? 'active' : ''}`}
                  aria-pressed={mode === 'flashcards'}
                  onClick={() => changeMode('flashcards')}
                >
                  <Icon name="BookOpen" size={15} />
                  Flashcards
                </button>
                <button
                  type="button"
                  className={`study-mode-option ${mode === 'quiz' ? 'active' : ''}`}
                  aria-pressed={mode === 'quiz'}
                  onClick={() => changeMode('quiz')}
                >
                  <Icon name="Check" size={15} />
                  Quiz
                </button>
              </div>
            </section>

            <section className="study-config-group">
              <span className="study-config-label">Documents</span>
              {indexedDocs.length ? (
                <div className="study-document-list">
                  {indexedDocs.map(document => {
                    const selected = selectedDocumentIds.some(
                      value => String(value) === String(document.id)
                    );
                    return (
                      <button
                        key={document.id}
                        type="button"
                        className={`study-doc-pill ${selected ? 'active' : ''}`}
                        aria-pressed={selected}
                        onClick={() => toggleDocument(document.id)}
                        title={document.file_name}
                      >
                        <Icon name="FileText" size={13} />
                        <span>{document.file_name}</span>
                        {selected && <Icon name="Check" size={13} />}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="study-config-note">
                  No indexed documents yet. Upload and index a source to begin.
                </p>
              )}
            </section>

            <section className="study-config-group">
              <span className="study-config-label">Items</span>
              <div className="study-chip-row">
                {COUNTS.map(value => (
                  <button
                    key={value}
                    type="button"
                    className={`study-chip ${count === value ? 'active' : ''}`}
                    aria-pressed={count === value}
                    onClick={() => changeCount(value)}
                  >
                    {value}
                  </button>
                ))}
              </div>
            </section>

            <section className="study-config-group">
              <span className="study-config-label">Difficulty</span>
              <div className="study-chip-row">
                {DIFFICULTIES.map(option => (
                  <button
                    key={option.value}
                    type="button"
                    className={`study-chip ${difficulty === option.value ? 'active' : ''}`}
                    aria-pressed={difficulty === option.value}
                    onClick={() => changeDifficulty(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </section>

            <button
              type="button"
              className="primary-button study-generate-button"
              onClick={handleGenerate}
              disabled={loading || !selectedDocumentIds.length}
            >
              {loading ? <span className="spinner" /> : <Icon name="Sparkles" size={15} />}
              {loading ? 'Generating…' : studySet ? 'Regenerate' : 'Generate Study Set'}
            </button>
            <p className="study-config-footnote">
              Study sets are generated on demand from indexed passages and are never stored.
            </p>
          </aside>

          <main className="study-stage">
            {loading ? (
              <div className="study-loading-card">
                <span className="study-loading-mark">
                  <Icon name="Sparkles" size={24} className="study-loading-spark" />
                </span>
                <h3>Building your study set</h3>
                <p>{studyStages[loadingStage]}</p>
                <div className="study-loading-bar"><i /></div>
              </div>
            ) : error ? (
              <div className="study-error-card">
                <Icon name="AlertCircle" size={26} />
                <h3>Could not generate a study set</h3>
                <p>{error}</p>
                <button type="button" className="secondary-button" onClick={handleGenerate}>
                  Try again
                </button>
              </div>
            ) : !studySet ? (
              <div className="study-empty-state">
                <span className="study-empty-mark">
                  <Icon name="Study" size={30} />
                </span>
                <h3>Turn your sources into active recall</h3>
                <p>
                  Choose documents, a format, and a difficulty, then generate a study set with
                  verifiable source citations.
                </p>
              </div>
            ) : studySet.mode === 'flashcards' ? (
              <div className="study-flashcards">
                <div className="study-set-meta">
                  <span>{cards.length} cards</span>
                  <span>Known {knownCount}</span>
                  <span>Review {reviewCount}</span>
                </div>

                {currentCard && (
                  <>
                    <div className="study-card-stage">
                      <div
                        className={`study-flashcard ${flipped ? 'flipped' : ''}`}
                        role="button"
                        tabIndex={0}
                        aria-pressed={flipped}
                        aria-label={`Flashcard ${cardIndex + 1} of ${cards.length}. ${currentCard.front}`}
                        onClick={handleCardClick}
                        onKeyDown={handleCardKeyDown}
                      >
                        <div className="study-card-face study-card-front">
                          <span className="study-card-kicker">PROMPT</span>
                          <h3>{currentCard.front}</h3>
                          <span className="study-card-hint">
                            Click or press Space to reveal the answer
                          </span>
                        </div>
                        <div className="study-card-face study-card-back">
                          <span className="study-card-kicker">ANSWER</span>
                          <MarkdownRenderer
                            content={currentCard.back}
                            sourceReferences={currentCard.source_references}
                            onCitation={handleCitation}
                          />
                          <span className="study-card-hint">
                            Click or press Space to return
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="study-card-controls">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => moveCard(-1)}
                        disabled={cardIndex === 0}
                      >
                        <Icon name="ChevronRight" size={15} className="study-icon-back" />
                        Previous
                      </button>
                      <span className="study-card-counter">
                        {cardIndex + 1} / {cards.length}
                      </span>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => moveCard(1)}
                        disabled={cardIndex === cards.length - 1}
                      >
                        Next
                        <Icon name="ChevronRight" size={15} />
                      </button>
                    </div>

                    <div className="study-self-check">
                      <span>How well did you know this?</span>
                      <button
                        type="button"
                        className={`study-self-button ${cardStatuses[currentCard.id] === 'known' ? 'active' : ''}`}
                        aria-pressed={cardStatuses[currentCard.id] === 'known'}
                        onClick={() => markCard('known')}
                      >
                        <Icon name="Check" size={14} />
                        Got it
                      </button>
                      <button
                        type="button"
                        className={`study-self-button ${cardStatuses[currentCard.id] === 'review' ? 'active' : ''}`}
                        aria-pressed={cardStatuses[currentCard.id] === 'review'}
                        onClick={() => markCard('review')}
                      >
                        Review again
                      </button>
                    </div>

                    <div className="study-source-scope">
                      <SourceCards
                        references={currentCard.source_references}
                        selected={selectedSource}
                        onInspect={handleCitation}
                        onDismiss={() => setSelectedSource(null)}
                      />
                    </div>
                  </>
                )}
              </div>
            ) : quizFinished ? (
              <div className="study-quiz-summary">
                <span className="study-summary-kicker">QUIZ COMPLETE</span>
                <h3>
                  {score} <span>/ {quizQuestions.length}</span>
                </h3>
                <p>{percentage}% accuracy across {quizQuestions.length} questions.</p>
                <div className="study-summary-bar">
                  <i style={{ width: `${percentage}%` }} />
                </div>
                <div className="study-summary-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => restartQuiz(true)}
                    disabled={!missedIds.length}
                  >
                    <Icon name="Search" size={15} />
                    Review Missed ({missedIds.length})
                  </button>
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => restartQuiz(false)}
                  >
                    <Icon name="Sparkles" size={15} />
                    Try Again
                  </button>
                </div>
              </div>
            ) : currentQuestion ? (
              <div className="study-quiz">
                <div className="study-quiz-head">
                  <div>
                    <span className="study-card-kicker">
                      QUESTION {questionIndex + 1} OF {quizQuestions.length}
                    </span>
                    <h3>{currentQuestion.question}</h3>
                  </div>
                  <span className="study-quiz-score">
                    <b>{score}</b> correct
                  </span>
                </div>

                <div
                  className="study-quiz-progress"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={quizQuestions.length}
                  aria-valuenow={answeredCount}
                >
                  <i style={{ width: `${quizProgress}%` }} />
                </div>

                <div className="study-options">
                  {currentQuestion.options.map((option, index) => (
                    <button
                      key={`${currentQuestion.id}-${index}`}
                      type="button"
                      className={optionClass(index)}
                      onClick={() => selectOption(index)}
                      disabled={currentSelection !== undefined}
                      aria-label={`Option ${optionLetter(index)}: ${option}`}
                    >
                      <span className="study-option-letter">{optionLetter(index)}</span>
                      <span className="study-option-text">{option}</span>
                      {currentSelection !== undefined
                        && index === currentQuestion.correct_index
                        && <Icon name="Check" size={15} />}
                      {currentSelection !== undefined
                        && index === currentSelection
                        && index !== currentQuestion.correct_index
                        && <Icon name="X" size={15} />}
                    </button>
                  ))}
                </div>

                {currentSelection !== undefined && (
                  <>
                    <div
                      className={`study-answer-note ${
                        currentSelection === currentQuestion.correct_index
                          ? 'correct'
                          : 'incorrect'
                      }`}
                    >
                      <Icon
                        name={
                          currentSelection === currentQuestion.correct_index
                            ? 'Check'
                            : 'AlertCircle'
                        }
                        size={15}
                      />
                      {currentSelection === currentQuestion.correct_index
                        ? 'Correct answer'
                        : `Not quite. The correct answer is ${optionLetter(currentQuestion.correct_index)}.`}
                    </div>

                    <div className="study-explanation">
                      <div className="study-explanation-head">
                        <span>EXPLANATION</span>
                      </div>
                      <MarkdownRenderer
                        content={currentQuestion.explanation}
                        sourceReferences={currentQuestion.source_references}
                        onCitation={handleCitation}
                      />
                      <SourceCards
                        references={currentQuestion.source_references}
                        selected={selectedSource}
                        onInspect={handleCitation}
                        onDismiss={() => setSelectedSource(null)}
                      />
                    </div>

                    <div className="study-quiz-actions">
                      <button
                        type="button"
                        className="primary-button"
                        onClick={goNextQuestion}
                      >
                        {questionIndex >= quizQuestions.length - 1 ? 'See Results' : 'Next Question'}
                        <Icon name="ChevronRight" size={15} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : null}
          </main>
        </div>
      </section>
    </div>
  );
}
