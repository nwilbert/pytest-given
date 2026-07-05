# pytest-given — pytest-given

## ✓ Steps pushed during fixture setup record into the fixture recording
`tests/unit/capture/test_collector.py::test_push_step_during_fixture_setup_records_into_recording` · happy-path

- **given** a «Fixture recording» under setup
- **when** a «Step» is pushed inside the fixture body
- **then** it is recorded as a child of the recording root

## ✓ Fixture-body steps do not leak into the active scenario
`tests/unit/capture/test_collector.py::test_push_step_routing_isolates_recording_from_scenario` · happy-path

- **given** an «Active scenario» with a «Fixture recording»
- **when** a «Step» is pushed inside the fixture body
- **then** the step lives only in the recording, not the scenario

## ✓ A fixture recording is deep-copied when grafted
`tests/unit/capture/test_collector.py::test_graft_recording_deep_copies_into_scenario` · happy-path

- **given** a «Fixture recording» with a nested child «Step»
- **when** a «Graft» copies it into the «Active scenario»
- **then** the scenario gains a deep copy of the recorded steps

## ✓ A leaf given is grafted as a childless given step
`tests/unit/capture/test_collector.py::test_graft_leaf_given_appends_childless_given_step` · happy-path

- **given** an «Active scenario» is being recorded
- **when** a leaf «Graft» appends a childless «Step»
- **then** the step is a given with no children

## ✓ Grafting with an override replaces the root label but keeps children
`tests/unit/capture/test_collector.py::test_graft_recording_override_replaces_root_narration_keeps_children` · happy-path

- **given** a «Fixture recording» whose root has a label and a child
- **when** a «Graft» supplies an override «Narration»
- **then** the grafted root shows the override text and keeps its children

## ✓ Grafting with no active scenario is a no-op
`tests/unit/capture/test_collector.py::test_graft_leaf_given_without_scenario_is_noop` · happy-path

- **given** a collector with no «Active scenario»
- **when** a leaf «Graft» runs
- **then** no scenario is recorded

## ✓ FileGlossary lookup is case-insensitive
`tests/unit/capture/test_file_glossary.py::test_lookup_is_case_insensitive` · happy-path

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «Term» is looked up in three different cases
- **then** every lookup resolves to one handle type and the same id

## ✓ Repeated lookups return the same handle
`tests/unit/capture/test_file_glossary.py::test_handles_are_memoized` · happy-path

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «Term» is looked up twice
- **then** both lookups return the one memoized handle

## ✓ File-loaded terms start kindless
`tests/unit/capture/test_file_glossary.py::test_terms_start_kindless` · kind-inference, happy-path

- **given** a Markdown glossary file with no kind column
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a «File glossary» loads it
- **then** each «Term» is «Kindless» until inference runs

## ✓ An unknown name raises with a suggestion
`tests/unit/capture/test_file_glossary.py::test_unknown_name_raises_with_suggestion` · validation

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a misspelt «Term» is looked up
- **then** a PytestGivenError is raised with a spelling hint

## ✓ Handles are usable inline in an activity
`tests/unit/capture/test_file_glossary.py::test_usable_inline_in_activity` · story-grammar

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** its handles build an «Activity»
- **then** each slot becomes a «Term ref»

## ✓ Calling a handle overrides its display
`tests/unit/capture/test_file_glossary.py::test_call_overrides_display` · story-grammar

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a handle is called to name an «Instance»
- **then** the «Term ref» carries the overridden display

## ✓ An explicit kind column sets term kinds
`tests/unit/capture/test_file_glossary.py::test_explicit_kind_column` · happy-path

- **given** a Markdown glossary with an explicit Kind column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    ```
- **when** the «File glossary» reads the Kind column
- **then** kinds come straight from the file, not «Kindless» inference

## ✓ A kind column can be selected by integer index
`tests/unit/capture/test_file_glossary.py::test_kind_column_by_integer_index` · happy-path

- **given** a Markdown glossary with the kind in the third column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    ```
- **when** the «File glossary» selects the kind column by index
- **then** the kinds are read from that column

## ✓ A work_object kind alias maps to the object kind
`tests/unit/capture/test_file_glossary.py::test_work_object_underscore_alias` · happy-path

- **given** a glossary whose Kind cell says work_object
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Room | y | work_object |
    ```
- **when** the «File glossary» parses the kind
- **then** it normalizes to the «Work Object» kind

## ✓ An unrecognised kind value is rejected
`tests/unit/capture/test_file_glossary.py::test_unrecognised_kind_value_raises` · validation

- **given** a glossary whose Kind cell holds an unknown value
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Wizard |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError names the unrecognised kind

## ✓ A missing glossary file is reported clearly
`tests/unit/capture/test_file_glossary.py::test_missing_file_raises` · validation

- **given** a path to a file that does not exist
- **when** a «File glossary» is opened on that path
- **then** a PytestGivenError reports the file is not found

## ✓ A term cell with no alphanumeric characters is rejected
`tests/unit/capture/test_file_glossary.py::test_empty_id_term_cell_raises` · validation

- **given** a row whose «Term» cell has no id-able characters
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | @#$ | some definition |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError is raised with file:line context

## ✓ Conflicting duplicate rows are rejected
`tests/unit/capture/test_file_glossary.py::test_conflicting_duplicate_rows_raise` · validation

- **given** two rows for one «Term» with different definitions
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | First definition. |
    | Guest | Second definition. |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError reports the conflicting rows

## ✓ A blank description normalizes to undefined
`tests/unit/capture/test_file_glossary.py::test_blank_description_cell_normalizes_to_none` · happy-path

- **given** a row whose description cell is blank
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest |   |
    ```
- **when** the «File glossary» parses it
- **then** the «Term» definition is None, i.e. «Undefined»

## ✓ Identical duplicate rows collapse to one term
`tests/unit/capture/test_file_glossary.py::test_idempotent_duplicate_rows_ok` · happy-path

- **given** two identical rows for the same «Term»
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | A person booking. |
    | Guest | A person booking. |
    ```
- **when** the «File glossary» parses them
- **then** they collapse to a single «Term»

## ✓ Calling FileGlossary looks up a known term
`tests/unit/capture/test_file_glossary.py::test_file_glossary_call_known_name_returns_handle` · happy-path

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a known «Term» is looked up by call
- **then** a «Deferred term» is returned

## ✓ FileGlossary is a closed vocabulary
`tests/unit/capture/test_file_glossary.py::test_file_glossary_call_unknown_name_raises` · validation

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** an unknown name is called
- **then** a PytestGivenError is raised — it never creates a «Term»

## ✓ Calling an actor names a distinct instance
`tests/unit/capture/test_glossary.py::test_actor_call_returns_instance_with_distinct_display` · happy-path

- **given** an «Actor» handle for Guest
- **when** the «Actor» is called with a name
- **then** an «Instance» with a distinct display is returned

## ✓ Calling a verb records an inflection of the same term
`tests/unit/capture/test_glossary.py::test_verb_call_returns_inflection_sharing_term_identity` · happy-path

- **given** a «Verb» handle for confirm
- **when** the «Verb» is called with a surface form
- **then** an «Inflection» sharing the verb identity is returned

## ✓ Registering an actor returns a typed handle
`tests/unit/capture/test_glossary.py::test_glossary_actor_registers_and_returns_handle` · happy-path

- **given** an empty glossary
- **when** an «Actor» is registered with a definition
- **then** a typed «Actor» handle with the «Actor» kind is returned

## ✓ Re-registering a term with matching fields is idempotent
`tests/unit/capture/test_glossary.py::test_glossary_re_registration_with_matching_fields_is_idempotent` · happy-path

- **given** an «Actor» already registered with a definition
- **when** the same name and definition are registered again
- **then** both handles share the one «Term»

## ✓ Re-registering a term with a different definition is rejected
`tests/unit/capture/test_glossary.py::test_glossary_re_registration_with_mismatched_definition_raises` · validation

- **given** an «Actor» already registered with one definition
- **when** the name is registered again with a different definition
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ The same name cannot be two different kinds
`tests/unit/capture/test_glossary.py::test_glossary_cross_kind_collision_raises` · validation

- **given** a name already registered as an «Actor»
- **when** the same name is registered as a «Verb»
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ Registering an actor captures its definition site
`tests/unit/capture/test_glossary.py::test_glossary_actor_captures_source` · happy-path

- **given** a rootdir-aware glossary
- **when** an «Actor» is registered
- **then** the «Term» records a «Source link» to this file

## ✓ Calling the glossary declares a kindless term
`tests/unit/capture/test_glossary.py::test_call_declares_kindless_term` · kind-inference, happy-path

- **given** an empty glossary
- **when** a «Term» is declared by call, without a kind
- **then** the «Term» is registered as «Kindless»

## ✓ Subscript looks up an already-declared term
`tests/unit/capture/test_glossary.py::test_subscript_get_only_returns_handle` · happy-path

- **given** a glossary with one declared «Term»
- **when** the name is looked up by subscript
- **then** the returned «Term» is the declared one

## ✓ Subscripting an unknown name raises with a hint
`tests/unit/capture/test_glossary.py::test_subscript_unknown_name_raises_with_hint` · validation

- **given** a glossary with one declared «Term»
- **when** a near-miss name is subscripted
- **then** a PytestGivenError is raised with a spelling hint

## ✓ Term kinds are inferred from activity-slot positions
`tests/unit/capture/test_kind_resolution.py::test_infers_actor_verb_object_by_position` · kind-inference, happy-path

- **given** a glossary of three «Kindless» «Term» entries
- **when** «Kind inference» runs over a «Story»
- **then** they resolve to «Actor», «Verb», «Work Object» by slot

## ✓ An actor slot anywhere wins over a noun slot elsewhere
`tests/unit/capture/test_kind_resolution.py::test_actor_anywhere_beats_object` · kind-inference, happy-path

- **given** a «Term» that sits in a noun slot in one «Story»
- **when** the same «Term» also appears in an «Actor» slot
- **then** its inferred kind is «Actor»

## ✓ A term used in no story stays kindless
`tests/unit/capture/test_kind_resolution.py::test_never_used_stays_kindless` · kind-inference, happy-path

- **given** a «Term» referenced by no «Story»
- **when** «Kind inference» runs with no stories
- **then** the «Term» remains «Kindless»

## ✓ A term in both a verb and a noun slot is a conflict
`tests/unit/capture/test_kind_resolution.py::test_verb_and_noun_conflict_raises` · kind-inference, validation

- **given** a «Kindless» «Term» used in a verb slot and a noun slot
- **when** kind resolution runs over both stories
- **then** a PytestGivenError names the conflicting term

## ✓ A declared kind consistent with its slot is kept
`tests/unit/capture/test_kind_resolution.py::test_declared_kind_verified_and_kept` · kind-inference, happy-path

- **given** a glossary with explicitly declared «Term» kinds
- **when** «Kind inference» runs over a matching «Story»
- **then** the declared kinds are verified and preserved

## ✓ A declared verb in an actor slot is rejected
`tests/unit/capture/test_kind_resolution.py::test_declared_verb_in_actor_slot_raises` · kind-inference, validation

- **given** a «Term» declared as a «Verb»
- **when** kind resolution places it in the «Actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A term used as both verb and actor is a conflict
`tests/unit/capture/test_kind_resolution.py::test_verb_and_actor_conflict_raises` · kind-inference, validation

- **given** a «Kindless» «Term» used in a verb slot and an actor slot
- **when** kind resolution runs over both stories
- **then** a PytestGivenError names the conflicting term

## ✓ A declared work object in an actor slot is rejected
`tests/unit/capture/test_kind_resolution.py::test_declared_object_in_actor_slot_raises` · kind-inference, validation

- **given** a «Term» declared as a «Work Object»
- **when** kind resolution places it in the «Actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A declared actor in a verb slot is rejected
`tests/unit/capture/test_kind_resolution.py::test_declared_actor_in_verb_slot_raises` · kind-inference, validation

- **given** a «Term» declared as an «Actor»
- **when** kind resolution places it at position 1 (the verb slot)
- **then** a PytestGivenError says an actor cannot fill the verb slot

## ✓ A conflict error names only the offending stories
`tests/unit/capture/test_kind_resolution.py::test_conflict_where_names_only_offending_stories` · kind-inference, validation

- **given** an «Actor» «Term» that also appears in a verb slot
- **when** kind resolution raises
- **then** only the offending story is named in the message

## ✓ A conflict message excludes stories with an unrelated slot
`tests/unit/capture/test_kind_resolution.py::test_inferred_conflict_where_excludes_unrelated_slot_stories` · kind-inference, validation

- **given** a «Kindless» «Term» used in verb, actor and noun slots
- **when** the verb-vs-actor conflict is raised
- **then** only the verb and actor stories are named, not the noun one

## ✓ A declared verb in a noun slot is rejected
`tests/unit/capture/test_kind_resolution.py::test_declared_verb_in_noun_slot_raises` · kind-inference, validation

- **given** a «Term» declared as a «Verb»
- **when** kind resolution places it at position ≥2 (a noun slot)
- **then** a PytestGivenError says a verb cannot fill the noun slot

## ✓ Slot positions alternate verb/noun after the actor
`tests/unit/capture/test_kind_resolution.py::test_slot_for_maps_odd_positions_to_verb` · kind-inference, happy-path

- **given** the five positions of a short activity path
- **when** the «Slot» rule is applied to each position
- **then** position 0 is the actor «Slot», then verb and noun alternate

## ✓ A pipe table parses into term and definition rows
`tests/unit/capture/test_markdown_glossary.py::test_parses_default_columns` · markdown, happy-path

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser reads it into rows for a «File glossary»
- **then** each row carries a «Term», definition and source line

## ✓ Multiple tables in one file are merged
`tests/unit/capture/test_markdown_glossary.py::test_merges_multiple_tables` · markdown, happy-path

- **given** a document containing two separate pipe tables
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    
    ## More
    
    | Term | Meaning |
    |---|---|
    | Search | Look up. |
    ```
- **when** the parser reads the whole document
- **then** every table contributes its «Term» rows

## ✓ Columns can be selected by header name
`tests/unit/capture/test_markdown_glossary.py::test_column_by_header_name_case_insensitive` · markdown, happy-path

- **given** a table with custom, differently-cased header names
  - 📎 Markdown document:
    ```
    | Word | Note | Role |
    |---|---|---|
    | Guest | x | Actor |
    ```
- **when** the parser selects columns by header name
- **then** the named columns are matched case-insensitively

## ✓ Escaped pipes are preserved in cells
`tests/unit/capture/test_markdown_glossary.py::test_escaped_pipe_in_cell` · markdown, happy-path

- **given** cells containing escaped pipe characters (\|)
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | A\|B | pipe\|here |
    ```
- **when** the parser splits the row
- **then** the escaped pipe survives as a literal pipe

## ✓ Tables inside fenced code blocks are skipped
`tests/unit/capture/test_markdown_glossary.py::test_skips_tables_in_fenced_code_blocks` · markdown, happy-path

- **given** a fenced code block that contains a look-alike table
  - 📎 Markdown document:
    ````
    ```
    | Term | Meaning |
    |---|---|
    | Fake | nope |
    ```
    
    | Term | Meaning |
    |---|---|
    | Real | yes |
    ````
- **when** the parser reads the document
- **then** only the real table outside the fence contributes rows

## ✓ A file with no pipe table is rejected
`tests/unit/capture/test_markdown_glossary.py::test_no_table_raises` · markdown, validation

- **given** a document with no pipe table
  - 📎 Markdown document:
    ```
    # Just a heading
    
    No tables here.
    ```
- **when** the parser reads it for a «File glossary»
- **then** no pipe table is reported

## ✓ A missing named column is rejected
`tests/unit/capture/test_markdown_glossary.py::test_missing_named_column_raises` · markdown, validation

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser selects a header name that is absent
- **then** a PytestGivenError names the missing column

## ✓ A column index out of range is rejected
`tests/unit/capture/test_markdown_glossary.py::test_index_out_of_range_raises` · markdown, validation

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser selects a column index past the table width
- **then** a PytestGivenError names the out-of-range column

## ✓ A data row with too few columns is rejected
`tests/unit/capture/test_markdown_glossary.py::test_data_row_with_fewer_columns_raises` · markdown, validation

- **given** a table with a data row narrower than its header
  - 📎 Markdown document:
    ```
    | Term | Meaning | Type |
    |---|---|---|
    | Guest | A person |
    | Room | A bookable room | place |
    ```
- **when** the parser reads the short row
- **then** a PytestGivenError points at the short row

## ✓ Bold term cells render as clean terms
`tests/unit/capture/test_markdown_glossary.py::test_strips_bold_from_term_cell` · markdown, happy-path

- **given** a «Term» cell written with **bold** emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | **Scenario** | A decorated test. |
    ```
- **when** the parser reads the term cell
- **then** the emphasis is unwrapped to the plain canonical

## ✓ Italic and inline-code term cells are unwrapped
`tests/unit/capture/test_markdown_glossary.py::test_strips_italic_and_inline_code_from_term_cell` · markdown, happy-path

- **given** «Term» cells using *italic* and `code` emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | *Step* | one. |
    | `given` | two. |
    ```
- **when** the parser reads the term cells
- **then** each unwraps to its plain text

## ✓ Underscores inside an identifier survive
`tests/unit/capture/test_markdown_glossary.py::test_preserves_underscores_inside_term_identifier` · markdown, happy-path

- **given** a «Term» literally named work_object
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | work_object | a thing. |
    ```
- **when** the parser reads the term cell
- **then** the single underscores are not treated as emphasis

## ✓ Emphasis is stripped from kind cells too
`tests/unit/capture/test_markdown_glossary.py::test_strips_emphasis_from_kind_cell` · markdown, happy-path

- **given** a Kind cell written with bold emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | **Actor** |
    ```
- **when** the parser reads the kind cell
- **then** the kind is unwrapped to plain text

## ✓ Definition markdown is left intact
`tests/unit/capture/test_markdown_glossary.py::test_leaves_description_markdown_intact` · markdown, happy-path

- **given** a definition cell rich with inline code
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | Scenario | A test decorated with `@scenario(...)`. |
    ```
- **when** the parser reads the row
- **then** the definition keeps its markup for the tooltip

## ✓ A pipe line without a separator is not a table
`tests/unit/capture/test_markdown_glossary.py::test_pipe_line_without_separator_is_skipped` · markdown, happy-path

- **given** prose containing a stray pipe, then a real table
  - 📎 Markdown document:
    ```
    This line has a | in it but no separator follows.
    Next line is not a separator.
    
    | Term | Meaning |
    |---|---|
    | Real | yes |
    ```
- **when** the parser reads the document
- **then** only the real pipe table produces rows

## ✓ An actor handle in a path becomes a term ref
`tests/unit/capture/test_story.py::test_path_dispatches_actor_to_activity_term_ref` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built from three glossary handles
- **then** the «Actor» slot becomes a «Term ref»

## ✓ An inflected verb keeps its term identity but shows the inflection
`tests/unit/capture/test_story.py::test_path_dispatches_inflected_verb_to_activity_term_ref_with_inflected_display` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a «Verb» handle called with an «Inflection»
- **when** it takes the verb slot of a «Path»
- **then** the «Term ref» shows the inflection over the same «Verb»

## ✓ A bare string in a path becomes a connective word
`tests/unit/capture/test_story.py::test_path_dispatches_bare_string_to_activity_word` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built with a bare word between term nodes
- **then** the bare word becomes an «Activity Part» word, not a «Term ref»

## ✓ A path needs at least an actor, a verb and a node
`tests/unit/capture/test_story.py::test_path_rejects_path_with_fewer_than_three_parts` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **when** a «Path» of only two parts is built
- **then** a PytestGivenError rejects it as too short

## ✓ Position 0 of a path must be an actor
`tests/unit/capture/test_story.py::test_path_rejects_work_object_in_position_0` · story-grammar, validation

- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built with a «Work Object» in position 0
- **then** a PytestGivenError says position 0 is the «Actor» slot

## ✓ A verb cannot open a path
`tests/unit/capture/test_story.py::test_path_rejects_verb_in_position_0` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Verb» is placed in position 0 of a «Path»
- **then** a PytestGivenError says position 0 is the «Actor» slot

## ✓ A bare string may stand in for the actor slot
`tests/unit/capture/test_story.py::test_path_allows_bare_string_in_position_0` · story-grammar, happy-path

- **given** a search verb
- **given** a Room work object
- **when** a bare string takes position 0 of a «Path»
- **then** it is accepted as an «Activity Part» word

## ✓ Position 1 of a path must be a verb
`tests/unit/capture/test_story.py::test_path_rejects_actor_in_position_1` · story-grammar, validation

- **given** a Guest actor
- **given** a Room work object
- **when** an «Actor» is placed in position 1 of a «Path»
- **then** a PytestGivenError says position 1 is the «Verb» slot

## ✓ A work object cannot fill the verb slot
`tests/unit/capture/test_story.py::test_path_rejects_work_object_in_position_1` · story-grammar, validation

- **given** a Guest actor
- **given** a Room work object
- **when** a «Work Object» is placed in position 1 of a «Path»
- **then** a PytestGivenError says position 1 is the «Verb» slot

## ✓ Position 2 of a path must be a noun
`tests/unit/capture/test_story.py::test_path_rejects_verb_in_position_2` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **when** a «Verb» is placed in position 2 of a «Path»
- **then** a PytestGivenError says position 2 is the noun slot

## ✓ A bare verb may sit between two real entity nodes
`tests/unit/capture/test_story.py::test_path_allows_bare_verb_between_term_nodes` · story-grammar, happy-path

- **given** a Guest actor
- **given** a Room work object
- **when** a bare verb sits between an «Actor» and a «Work Object»
- **then** the entities are term refs and the verb stays a bare word

## ✓ A path may be fully bare words
`tests/unit/capture/test_story.py::test_path_allows_fully_bare_path` · story-grammar, happy-path

- **given** three plain words with no glossary handles
- **when** a «Path» is built from them
- **then** every part is an «Activity Part» word

## ✓ Node/edge alternation allows a trailing connective node
`tests/unit/capture/test_story.py::test_path_allows_node_edge_alternation_with_connective` · story-grammar, happy-path

- **given** an «Actor», a «Verb», a «Work Object» and a second actor
- **when** they form a five-part «Path» joined by a connective
- **then** even positions are term-ref nodes and the connective stays a word

## ✓ A path may not end on a dangling edge
`tests/unit/capture/test_story.py::test_path_rejects_dangling_edge` · story-grammar, validation

- **given** an «Actor», «Verb» and «Work Object» plus a connective
- **when** a path ending on a connective edge is built
- **then** a PytestGivenError rejects the dangling edge

## ✓ A single-path activity synthesizes one path
`tests/unit/capture/test_story.py::test_activity_single_path_synthesizes_one_path` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** an «Activity» is built from handles directly
- **then** it wraps a single «Path»

## ✓ An activity may branch into multiple paths
`tests/unit/capture/test_story.py::test_activity_multi_path_accepts_multiple_paths` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two alternate «Path» branches
- **when** they are combined into one «Activity»
- **then** the activity carries both paths

## ✓ Mixing loose parts and prebuilt paths is rejected
`tests/unit/capture/test_story.py::test_activity_mixing_parts_and_paths_raises` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a prebuilt «Path»
- **when** it is combined with loose handles in one «Activity»
- **then** a PytestGivenError rejects the mix

## ✓ Activity id 0 is reserved
`tests/unit/capture/test_story.py::test_activity_explicit_id_zero_raises` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** an «Activity» is built with explicit id=0
- **then** a PytestGivenError says id=0 is reserved

## ✓ A story auto-numbers its activities from one
`tests/unit/capture/test_story.py::test_story_auto_numbers_activities_from_one` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Story» is built from two «Activity» rows
- **then** the activities are numbered 1 and 2

## ✓ Auto-numbering skips ids already taken explicitly
`tests/unit/capture/test_story.py::test_story_auto_numbering_skips_taken_explicit_ids` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a mix of explicit and auto «Activity» ids
- **when** they are assembled into a «Story»
- **then** auto picks skip the ids already used explicitly

## ✓ Duplicate activity ids in a story are rejected
`tests/unit/capture/test_story.py::test_story_rejects_duplicate_activity_ids` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two «Activity» rows sharing an explicit id
- **when** they are assembled into a «Story»
- **then** a PytestGivenError reports the duplicate activity id

## ✓ A story derives its id from its title
`tests/unit/capture/test_story.py::test_story_derives_id_from_title` · story-grammar, happy-path

- **given** a human-readable story title
- **when** a «Story» is built from it
- **then** its id is the slugified title

## ✓ A story may span only one glossary
`tests/unit/capture/test_story.py::test_story_rejects_two_glossaries` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two activities that reach two different glossaries
- **when** a «Story» is built spanning both glossaries
- **then** a PytestGivenError says a story spans multiple glossaries

## ✓ Two stories with the same id collide
`tests/unit/capture/test_story.py::test_story_id_collision_raises_with_both_sites` · story-grammar, validation

- **given** a «Story» already declared under an id
- **when** a second story is declared with the same slug
- **then** a PytestGivenError reports the id was already declared

## ✓ A path may chain a second verb-object pair
`tests/unit/capture/test_story.py::test_path_allows_second_verb_edge` · story-grammar, happy-path

- **given** an «Actor», two «Verb» and two «Work Object» handles
- **when** they form a five-node «Path» (actor verb object verb object)
- **then** every slot is a «Term ref», with no bare words

## ✓ A Template parses a bare placeholder
`tests/unit/capture/test_template.py::test_template_parses_single_placeholder` · step-text, parametrization

- **given** a deferred «Templatize» template with one placeholder
- **when** the template is parsed
- **then** it splits into literal and placeholder «Narration» parts

## ✓ A Template substitutes parametrize values
`tests/unit/capture/test_template.py::test_template_substitute_basic` · step-text, parametrization

- **given** a «Templatize» template referencing a «Case» column
- **when** a «Parameter table» value is substituted in
- **then** the placeholder is filled with that value

## ✓ A t-string interpolation becomes a value part
`tests/unit/capture/test_template.py::test_parse_tstring_single_interpolation` · step-text, happy-path

- **given** a t-string step with one interpolated value
- **when** the t-string is parsed at runtime
- **then** the interpolation becomes a «Narration» value part

## ✓ A t-string can interpolate an arbitrary expression
`tests/unit/capture/test_template.py::test_parse_tstring_expression` · step-text, happy-path

- **given** a t-string step interpolating a computed expression
- **when** the t-string is parsed
- **then** the «Value highlight» part records the full expression

## ✓ A glossary handle in a t-string emits a term ref
`tests/unit/capture/test_template.py::test_tstring_with_actor_emits_term_ref` · step-text

- **given** an «Actor» handle from the glossary
- **when** the handle is interpolated into a t-string step
- **then** the step carries a «Term ref» pill for that «Actor»

## ✓ A work object handle in a t-string emits a term ref
`tests/unit/capture/test_template.py::test_tstring_with_work_object_emits_term_ref` · step-text

- **given** a «Work Object» handle from the glossary
- **when** it is interpolated into a t-string step
- **then** the step carries a «Term ref» for that «Work Object»

## ✓ A bare verb handle keeps its canonical display
`tests/unit/capture/test_template.py::test_tstring_with_verb_emits_term_ref_with_canonical_display` · step-text

- **given** a «Verb» handle used without an «Inflection»
- **when** it is interpolated into a t-string step
- **then** the «Term ref» shows the canonical verb

## ✓ An inflected verb in a t-string shows the inflection
`tests/unit/capture/test_template.py::test_tstring_with_inflected_verb_emits_term_ref_with_inflected_display` · step-text

- **given** a «Verb» handle called with an «Inflection»
- **when** it is interpolated into a t-string step
- **then** the «Term ref» shows the inflection but keeps the verb id

## ✓ A term ref may not carry a format spec
`tests/unit/capture/test_template.py::test_tstring_term_ref_with_format_spec_raises` · step-text, validation

- **given** an «Actor» handle interpolated with a format spec
- **when** the t-string is parsed
- **then** a PytestGivenError says a «Term ref» takes no format spec

## ✓ A FileGlossary handle works in a t-string step
`tests/unit/capture/test_template.py::test_tstring_with_file_term_handle_emits_term_ref` · step-text

- **given** a «Deferred term» from a «File glossary»
- **when** it is interpolated into a t-string step
- **then** the step carries a single «Term ref» pill

## ✓ A verb activity ref has one identity regardless of inflection
`tests/unit/report/test_coverage.py::test_identity_of_activity_term_ref_verb_ignores_display` · happy-path

- **given** a «Verb» written canonically and as an «Inflection»
- **when** «Coverage» derives each «Term ref» identity
- **then** both collapse to the one canonical verb identity

## ✓ A branching activity unions references across its paths
`tests/unit/report/test_coverage.py::test_a_refs_unions_across_multi_path_activity` · happy-path

- **given** an «Activity» that branches into two «Path» alternatives
- **when** «Coverage» collects the «Activity» references
- **then** both «Instance» identities across the branches are present

## ✓ An instance step ref adds a canonical fallback
`tests/unit/report/test_coverage.py::test_s_for_step_instance_entity_ref_adds_canonical_fallback` · happy-path

- **given** a «Step» referring to a named «Instance»
- **when** «Coverage» computes the identity set for the «Step»
- **then** it includes the canonical «Term ref» fallback

## ✓ A verb ref always resolves to its canonical identity
`tests/unit/report/test_coverage.py::test_s_for_step_verb_ref_always_canonical` · happy-path

- **given** a «Step» using an «Inflection» of a «Verb»
- **when** «Coverage» computes its identity set
- **then** the identity ignores the surface form and stays canonical

## ✓ An unknown term ref is skipped
`tests/unit/report/test_coverage.py::test_s_for_step_unknown_term_ref_skipped` · validation

- **given** a «Step» referencing a «Term» not in the glossary
- **when** «Coverage» computes its identity set
- **then** the unknown ref contributes nothing to the identity set

## ✓ An instance step covers a canonical activity
`tests/unit/report/test_coverage.py::test_compute_coverage_covers_canonical_activity_via_instance_step` · happy-path

- **given** a «Story» with a canonical «Activity»
- **when** a «Scenario» step names a specific «Instance»
- **then** «Coverage» reports the «Activity» as covered

## ✓ A canonical step does not cover an instance activity
`tests/unit/report/test_coverage.py::test_compute_coverage_does_not_cover_instance_activity_with_canonical_step` · happy-path

- **given** an «Activity» anchored to a named «Instance»
- **when** a «Scenario» step only names the canonical «Actor»
- **then** «Coverage» leaves the more specific instance activity uncovered

## ✓ A scenario activity binding constrains coverage
`tests/unit/report/test_coverage.py::test_compute_coverage_scenario_constrained_to_activity_ids` · happy-path

- **given** a «Story» with two matching activities
- **when** the «Scenario» binds only to activity 1
- **then** «Coverage» considers only the bound «Activity»

## ✓ An activity with two distinct terms is coverage-eligible
`tests/unit/report/test_coverage.py::test_is_coverage_eligible_true_for_two_distinct_terms` · happy-path

- **given** an «Activity» anchored by two distinct «Term» refs
- **when** its «Coverage» eligibility is checked
- **then** it is eligible for «Coverage» tracking

## ✓ An under-anchored activity is not coverage-eligible
`tests/unit/report/test_coverage.py::test_is_coverage_eligible_false_for_one_distinct_term` · happy-path

- **given** an «Activity» that mentions only one distinct «Term»
- **when** its «Coverage» eligibility is checked
- **then** it is ineligible — «Coverage» needs at least two anchors

## ✓ An under-anchored activity is never reported as covered
`tests/unit/report/test_coverage.py::test_compute_coverage_excludes_under_anchored_activity` · happy-path

- **given** a «Story» whose «Activity» is all bare words
- **when** coverage is computed against a scenario
- **then** «Coverage» excludes the under-anchored «Activity»

## ✓ Nested steps are walked for coverage
`tests/unit/report/test_coverage.py::test_compute_coverage_nested_steps_are_walked` · happy-path

- **given** a «Story» with one canonical «Activity»
- **when** the covering «Term ref»s live in a nested child «Step»
- **then** the nested «Step» still counts and the «Activity» is covered

## ✓ An explicit step binding covers an eligible activity
`tests/unit/report/test_coverage.py::test_compute_coverage_explicit_step_binding_covers_eligible_activity` · happy-path

- **given** a «Story» with a coverage-eligible «Activity»
- **when** a «Step» binds to it explicitly by id
- **then** «Coverage» counts it directly, without identity matching

## ✓ An explicit binding still requires eligibility
`tests/unit/report/test_coverage.py::test_compute_coverage_explicit_binding_ignored_for_ineligible_activity` · validation

- **given** a «Story» whose «Activity» is under-anchored
- **when** a «Step» binds to it explicitly by id
- **then** eligibility gates the binding, so «Coverage» stays empty

## ✓ Term ids are derived as URL-safe slugs · 8 cases
`tests/unit/capture/test_glossary.py::test_id_derive_produces_expected_slug[Guest-guest]` · happy-path

- **given** the name {text}
- **when** it is slugified into a «Term» id
- **then** the id is the expected slug {expected}

| text | expected | |
|---|---|---|
| Guest | guest | ✓ |
| Order received | order-received | ✓ |
|   Work Object   | work-object | ✓ |
| do_the_thing | do-the-thing | ✓ |
| Buy / sell | buy-sell | ✓ |
| Guest #1 | guest-1 | ✓ |
| café | caf | ✓ |
| booking system | booking-system | ✓ |

## ✓ A name with no id-able characters is rejected · 4 cases
`tests/unit/capture/test_glossary.py::test_id_derive_raises_on_empty_result[---]` · validation

- **given** the name {text}
- **when** it is slugified into a «Term» id
- **then** a PytestGivenError reports the derived id is empty

| text | |
|---|---|
| --- | ✓ |
|     | ✓ |
|  | ✓ |
| ### | ✓ |

## ✓ A Template accepts bare identifiers only · 3 cases
`tests/unit/capture/test_template.py::test_template_non_identifier_raises_pytest_given_error[attribute]` · step-text, validation

- **given** the placeholder {text}
- **when** a «Templatize» template is built from it
- **then** a PytestGivenError says bare identifiers only

| text | |
|---|---|
| count={obj.attr} | ✓ |
| {d[key]} | ✓ |
| {x + 1} | ✓ |
