from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    Glossary,
    Story,
    StoryId,
    TermId,
)
from pytest_given.report.diagram import build_graph


def test_actors_dedupe_story_wide(trip_story: Story, trip_glossary: Glossary) -> None:
    graph = build_graph(trip_story, trip_glossary)
    actor_labels = sorted(n.label for n in graph.nodes if n.glyph == 'actor')
    assert actor_labels == ['Alice', 'Bob', 'Booking System', 'Carol']


def test_work_objects_repeat_per_activity_dedupe_within(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    booking_nodes = [n for n in graph.nodes if n.label == 'Booking']
    # Activity 1 references Booking in both paths -> one node; activity 2 -> another.
    assert len(booking_nodes) == 2
    assert len({n.id for n in booking_nodes}) == 2


def test_edge_numbering_first_edge_of_each_path(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    numbered = [e for e in graph.edges if e.number is not None]
    # Activity 1 has two paths -> two edges numbered 1; activities 2-4 one each.
    assert sorted(e.number for e in numbered) == [1, 1, 2, 3, 4]
    connectives = [e for e in graph.edges if e.connective]
    assert {e.label for e in connectives} == {'to', 'redeems'}
    assert all(e.number is None for e in connectives if e.label == 'to')


def test_verb_edges_carry_their_glossary_term(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    by_label = {}
    for edge in graph.edges:
        by_label.setdefault(edge.label, edge)
    # A glossary verb carries its term id, so the diagram can surface its
    # definition on hover -- the glossary reaches the verbs, not just the nodes.
    assert by_label['adds'].term_id == TermId('add')
    assert by_label['confirms'].term_id == TermId('confirm')
    assert by_label['sends'].term_id == TermId('send')
    # Bare-word connectives are not glossary terms: no term id, no tooltip.
    assert by_label['to'].term_id is None
    assert by_label['redeems'].term_id is None


def test_kindless_term_is_work_object_off_position_zero(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    loyalty = [n for n in graph.nodes if n.label == 'loyalty points']
    assert len(loyalty) == 1
    assert loyalty[0].glyph == 'work'


def test_instance_display_gets_canonical_sublabel(
    trip_story: Story, trip_glossary: Glossary
) -> None:
    graph = build_graph(trip_story, trip_glossary)
    carol = next(n for n in graph.nodes if n.label == 'Carol')
    assert carol.sublabel == 'Organizer'
    system = next(n for n in graph.nodes if n.label == 'Booking System')
    assert system.sublabel is None  # display == canonical


def test_no_glossary_position_zero_word_is_actor() -> None:
    from pytest_given.model import ActivityWord

    story = Story(
        id=StoryId('s'),
        title='S',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            ActivityWord(text='someone'),
                            ActivityWord(text='does'),
                            ActivityWord(text='something'),
                        )
                    ),
                ),
            ),
        ),
    )
    graph = build_graph(story, None)
    by_label = {n.label: n for n in graph.nodes}
    assert by_label['someone'].glyph == 'actor'
    assert by_label['something'].glyph == 'work'
    assert by_label['someone'].term_id is None
