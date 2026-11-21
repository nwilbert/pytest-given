import pytest

from pytest_given.model import (
    Clause,
    Definition,
    Glossary,
    GlossaryTerm,
    NarrationLiteral,
    NarrationTermRef,
    Sentence,
    SentenceId,
    Story,
    StoryId,
    TermId,
)


def term_ref(term_id: str, display: str) -> NarrationTermRef:
    return NarrationTermRef(term_id=TermId(term_id), display=display)


@pytest.fixture
def trip_glossary() -> Glossary:
    return Glossary(
        terms=[
            GlossaryTerm(
                id=TermId('organizer'),
                kind='actor',
                canonical='Organizer',
                definition=Definition.literal('Books on behalf of a group.'),
            ),
            GlossaryTerm(
                id=TermId('guest'),
                kind='actor',
                canonical='Guest',
                definition=Definition.literal('Individual traveler.'),
            ),
            GlossaryTerm(
                id=TermId('booking-system'),
                kind='actor',
                canonical='Booking System',
                definition=Definition.literal('Reservation back-end.'),
            ),
            GlossaryTerm(
                id=TermId('booking'),
                kind='object',
                canonical='Booking',
                definition=Definition.literal('A reservation.'),
            ),
            GlossaryTerm(
                id=TermId('confirmation'),
                kind='object',
                canonical='Confirmation',
                definition=Definition.literal('Success notification.'),
            ),
            GlossaryTerm(id=TermId('add'), kind='sentence', canonical='add'),
            GlossaryTerm(id=TermId('confirm'), kind='sentence', canonical='confirm'),
            GlossaryTerm(id=TermId('send'), kind='sentence', canonical='send'),
            GlossaryTerm(
                id=TermId('loyalty-points'), kind=None, canonical='loyalty points'
            ),
        ]
    )


@pytest.fixture
def trip_story() -> Story:
    return Story(
        id=StoryId('book-a-trip'),
        title='Book a Trip',
        sentences=(
            # 1: multi-clause — organizer adds each guest to the same booking.
            Sentence(
                id=SentenceId(1),
                clauses=(
                    Clause(
                        parts=(
                            term_ref('organizer', 'Carol'),
                            term_ref('add', 'adds'),
                            term_ref('guest', 'Alice'),
                            NarrationLiteral(value='to'),
                            term_ref('booking', 'Booking'),
                        )
                    ),
                    Clause(
                        parts=(
                            term_ref('organizer', 'Carol'),
                            term_ref('add', 'adds'),
                            term_ref('guest', 'Bob'),
                            NarrationLiteral(value='to'),
                            term_ref('booking', 'Booking'),
                        )
                    ),
                ),
            ),
            # 2: work object repeated in a new sentence.
            Sentence(
                id=SentenceId(2),
                clauses=(
                    Clause(
                        parts=(
                            term_ref('booking-system', 'Booking System'),
                            term_ref('confirm', 'confirms'),
                            term_ref('booking', 'Booking'),
                        )
                    ),
                ),
            ),
            # 3: recipient actor + kindless term.
            Sentence(
                id=SentenceId(3),
                clauses=(
                    Clause(
                        parts=(
                            term_ref('booking-system', 'Booking System'),
                            term_ref('send', 'sends'),
                            term_ref('confirmation', 'Confirmation'),
                            NarrationLiteral(value='to'),
                            term_ref('guest', 'Alice'),
                        )
                    ),
                ),
            ),
            Sentence(
                id=SentenceId(4),
                clauses=(
                    Clause(
                        parts=(
                            term_ref('organizer', 'Carol'),
                            NarrationLiteral(value='redeems'),
                            term_ref('loyalty-points', 'loyalty points'),
                        )
                    ),
                ),
            ),
        ),
    )
