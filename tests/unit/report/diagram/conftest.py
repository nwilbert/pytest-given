import pytest

from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    GlossaryTerm,
    Story,
    StoryId,
    TermId,
)


def term_ref(term_id: str, display: str) -> ActivityTermRef:
    return ActivityTermRef(term_id=TermId(term_id), display=display)


@pytest.fixture
def trip_glossary() -> Glossary:
    return Glossary(
        terms=[
            GlossaryTerm(id=TermId('organizer'), kind='actor', canonical='Organizer',
                         definition='Books on behalf of a group.'),
            GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest',
                         definition='Individual traveler.'),
            GlossaryTerm(
                id=TermId('booking-system'), kind='actor',
                canonical='Booking System', definition='Reservation back-end.',
            ),
            GlossaryTerm(id=TermId('booking'), kind='object', canonical='Booking',
                         definition='A reservation.'),
            GlossaryTerm(id=TermId('confirmation'), kind='object',
                         canonical='Confirmation', definition='Success notification.'),
            GlossaryTerm(id=TermId('add'), kind='verb', canonical='add'),
            GlossaryTerm(id=TermId('confirm'), kind='verb', canonical='confirm'),
            GlossaryTerm(id=TermId('send'), kind='verb', canonical='send'),
            GlossaryTerm(id=TermId('loyalty-points'), kind=None,
                         canonical='loyalty points'),
        ]
    )


@pytest.fixture
def trip_story() -> Story:
    return Story(
        id=StoryId('book-a-trip'),
        title='Book a Trip',
        activities=(
            # 1: multi-path — organizer adds each guest to the same booking.
            Activity(id=ActivityId(1), paths=(
                ActivityPath(parts=(
                    term_ref('organizer', 'Carol'), term_ref('add', 'adds'),
                    term_ref('guest', 'Alice'), ActivityWord(text='to'),
                    term_ref('booking', 'Booking'),
                )),
                ActivityPath(parts=(
                    term_ref('organizer', 'Carol'), term_ref('add', 'adds'),
                    term_ref('guest', 'Bob'), ActivityWord(text='to'),
                    term_ref('booking', 'Booking'),
                )),
            )),
            # 2: work object repeated in a new activity.
            Activity(id=ActivityId(2), paths=(
                ActivityPath(parts=(
                    term_ref('booking-system', 'Booking System'),
                    term_ref('confirm', 'confirms'), term_ref('booking', 'Booking'),
                )),
            )),
            # 3: recipient actor + kindless term.
            Activity(id=ActivityId(3), paths=(
                ActivityPath(parts=(
                    term_ref('booking-system', 'Booking System'),
                    term_ref('send', 'sends'), term_ref('confirmation', 'Confirmation'),
                    ActivityWord(text='to'), term_ref('guest', 'Alice'),
                )),
            )),
            Activity(id=ActivityId(4), paths=(
                ActivityPath(parts=(
                    term_ref('organizer', 'Carol'), ActivityWord(text='redeems'),
                    term_ref('loyalty-points', 'loyalty points'),
                )),
            )),
        ),
    )
